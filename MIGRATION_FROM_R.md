# Migration from R — Logic Porting Reference

This document maps original R functions to Python implementations. **Behavior must match** for filter/group/cohort calculations.

---

## Package mapping

| R Package | Python Equivalent |
|-----------|-------------------|
| shiny | FastAPI + HTML/JS (no direct equivalent) |
| bslib | Custom CSS (Bootstrap 5 optional) |
| dplyr | pandas or Polars |
| ggplot2 | matplotlib / plotly |
| plotly (R) | plotly.js (frontend) or plotly.py (backend PNG) |
| lubridate | pandas datetime / python-dateutil |
| DT | DataTables.js or custom table |
| readr | pandas `read_csv` |
| shinymanager | Custom JWT auth |
| shinyWidgets | Custom multi-select components |
| DBI + duckdb | asyncpg / SQLAlchemy + Supabase Postgres |
| scrypt | passlib.hash.scrypt |
| blastula | Resend / SendGrid |
| openxlsx | openpyxl (if Excel export needed) |
| rmarkdown | WeasyPrint / Jinja2 templates |
| jsonlite | json (stdlib) |

---

## `filter_data(dat0, input, is_admin)` → Python

```python
def filter_data(df: pd.DataFrame, filters: FilterState, is_admin: bool) -> pd.DataFrame:
  if filters.year is None:
    raise ValueError("Year is required")

  out = df[df["date"].dt.year == filters.year]

  if filters.month and filters.month != "All":
    month_num = list(calendar.month_name).index(filters.month)
    out = out[out["date"].dt.month == month_num]

  if filters.day and filters.day != "All":
    out = out[out["date"].dt.day == int(filters.day)]

  if filters.sex and "Overall" not in filters.sex:
    out = out[out["sex"].isin(filters.sex)]

  if filters.treatment and "Overall" not in filters.treatment:
    if "No Treatment" in filters.treatment:
      non_null = [t for t in filters.treatment if t != "No Treatment"]
      if non_null:
        out = out[out["treatment"].isna() | out["treatment"].isin(non_null)]
      else:
        out = out[out["treatment"].isna()]
    else:
      out = out[out["treatment"].isin(filters.treatment)]

  if filters.breed and "Overall" not in filters.breed:
    out = out[out["breed"].isin(filters.breed)]

  if filters.mob and "Overall" not in filters.mob:
    out = out[out["mob"].isin(filters.mob)]

  if is_admin and filters.eid and "Overall" not in filters.eid:
    out = out[out["eid"].isin(filters.eid)]

  return out
```

---

## `create_simplified_group_labels(df, input)` → Python

Port lines 99–209 of `filter.R` exactly:

1. Get unique combos of (sex, treatment, breed, mob, eid)
2. Single combo + all "Overall" → `"Overall Average"`
3. Single combo otherwise → full label with all dimension names
4. Multiple combos → find `varying_cols` where `nunique > 1`
5. If no varying cols → same as single combo logic
6. Else per row: join only varying cols as `"Sex: Steer | Treatment: Drench"`
7. NA treatment → `"No Treatment"`

---

## `create_full_group_labels(df, input)` → Python

Always include ALL dimensions in label:
`"Sex: Steer, Treatment: Drench, Breed: Brahman X, Mob: Front, EID: 982..."`

Use `"EID"` not `"Eid"` for column name in label.

---

## `grouped_data` reactive → Python

This is the most complex port. Logic from `filter.R` lines 592–719:

### Determine filter expansion per dimension

For each of sex, treatment, breed, mob, eid:

```python
has_all = "Overall" in selected_values
has_specific = len(selected_values) > 1 and any(v != "Overall" for v in selected_values)

if has_all and not has_specific:
    values = ["Overall"]
elif has_all and has_specific:
    values = ["Overall"] + [v for v in selected_values if v != "Overall"]
elif not has_all and has_specific:
    values = selected_values
else:
    values = unique_values_from_data  # treatment NA → "No Treatment"
```

For non-admin: `eid` always `["Overall"]`, `eid_specific = False`.

### Build combinations
```python
import itertools
combos = itertools.product(sex_values, treatment_values, breed_values, mob_values, eid_values)
```

### Filter base_df for each combo
For each combo, filter rows where each column matches OR dimension is "Overall" (no filter on that dimension).

Treatment matching: `"No Treatment"` matches `treatment IS NULL`.

### Assign group label
Use `create_simplified_group_labels` on resulting subset.

Concatenate all subsets → `grouped_data` DataFrame.

---

## `kpi_block(df, measure)` → Python

```python
def kpi_block(df, measure: str) -> dict:
  if df.empty or not pd.api.types.is_numeric_dtype(df[measure]):
    return {"mean": 0, "display": "No data"}
  m = df[measure].dropna()
  unit = MEASURE_UNITS.get(measure.lower(), "")
  return {
    "mean": round(m.mean(), 2),
    "min": round(m.min(), 2),
    "max": round(m.max(), 2),
    "median": round(m.median(), 2),
    "count": int(m.count()),
    "unit": unit,
  }
```

Format: `$` prefix for animalvalue; suffix for others.

---

## `subset_by_window(df, days)` → Python

```python
def subset_by_window(df, days: int) -> pd.DataFrame:
  if df.empty:
    return df
  dmax = df["date"].max()
  return df[(df["date"] >= dmax - pd.Timedelta(days=days - 1)) & (df["date"] <= dmax)]
```

Windows: 1, 15, 31 days.

---

## Time series aggregation

```python
df_daily = grouped_df.groupby(["date", "group"]).agg(
  value=(measure, "mean"),
  count=(measure, "count")
).reset_index()
```

Optional LOESS smooth: `statsmodels.nonparametric.smoothers_lowess.lowess` or scipy.

---

## Distribution sampling (performance)

From `distribution.R`:

| Total rows | Action |
|------------|--------|
| > 5000 | sample 500 per group |
| > 2000 | sample 300 per group |
| Histogram > 3000 | sample 200 per group |

```python
def sample_for_distribution(df, max_per_group=500):
  if len(df) <= 2000:
    return df
  return df.groupby("group", group_keys=False).apply(
    lambda g: g.sample(n=min(max_per_group, len(g)), random_state=42)
  )
```

---

## Cohort logic

From `cohorts_page.R`:

```python
def analyze_cohorts(df, measure, percentile=10):
  # Mixed warning
  mixed = any_has_overall_and_specific(filters)

  per_animal = df.groupby("eid")[measure].mean().reset_index(name="avg")
  per_animal = per_animal.sort_values("avg", ascending=False)

  n = len(per_animal)
  k = math.ceil(n * percentile / 100)

  top = per_animal.head(k)
  bottom = per_animal.tail(k)

  return top, bottom, mixed
```

---

## `friendly_label(col)` → Python

```python
def friendly_label(col: str) -> str:
  if col in ("treatment", "treatment_display"):
    return "Treatment"
  if col == "eid":
    return "EID"
  if col == "date":
    return "Date"
  if col in MEASURE_LABELS:
    return MEASURE_LABELS[col]
  return col.replace("_", " ").title()
```

---

## Customise chart aggregation

From `customise.R` — support agg functions: mean, sum, count, min, max

For bar/line with grouping:
```python
df.groupby([x_col, group_col])[y_col].agg(agg_fun).reset_index()
```

Histogram: no y_col, bins parameter.

---

## `get_common_filters_note(df, input)` → Python

Returns string when comparing groups, e.g. `"Comparing groups by Sex only"`.

Logic: inspect which filter dimensions have multiple selected specific values (not Overall) and are varying in grouped data.

---

## Debouncing

R used `debounce(reactive(...), 300)` for filters and measure.

Python/JS: lodash debounce or custom 300ms timer on filter change events.

---

## Timezone

R: `Sys.setenv(TZ = "Australia/Sydney")`

Python:
```python
import os
os.environ["TZ"] = "Australia/Sydney"
# or use zoneinfo everywhere
```

---

## Database query optimization

Original DuckDB indexes — replicate in Postgres:
```sql
CREATE INDEX idx_animal_farm_date ON animal_data (farm_id, date);
-- etc. see 001_schema.sql
```

Original `load_data()` built dynamic SQL with parameterized WHERE — port to SQLAlchemy or raw asyncpg with `$1` params for server-side filtering on large datasets.

For MVP, load filtered data in pandas after SQL WHERE on indexed columns.

---

## What NOT to port

| R artifact | Reason |
|------------|--------|
| `rsconnect::deployApp` | Use Vercel git deploy |
| `secure_app()` wrapper | Custom login page |
| `addResourcePath("logo")` | Supabase Storage URLs |
| Shiny `observeEvent` patterns | JS event listeners |
| `onStop()` DB disconnect | Connection pooling handles this |
| Windows `.bat` files | Python CLI |

---

## Validation: parity test cases

Create pytest fixtures with small DataFrame (20 rows) and verify:

| Test | Input | Expected |
|------|-------|----------|
| Year filter only | year=2023 | all 2023 rows |
| Month filter | October | month==10 |
| Treatment NULL | "No Treatment" selected | rows where treatment is null |
| Overall sex | sex=["Overall"] | no sex filter |
| Mixed sex | sex=["Overall", "Steer"] | grouped expansion includes both |
| Non-admin EID | user role | eids not in response |
| Cohort 10% | 100 animals | top 10, bottom 10 |
| KPI last day | known dates | only max date rows |

Compare outputs against R `filter_data()` unit tests in original `tests/testthat/`.
