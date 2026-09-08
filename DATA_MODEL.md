# Data Model

## CSV upload format

### File naming
```
{farm_id}_YYYY-MM-DD.csv
```
Examples: `KF_2025-01-22.csv`, `FarmA_initial.csv`

### Required columns
| CSV Header | DB Column | Type | Notes |
|------------|-----------|------|-------|
| EID | eid | text | Electronic ID; may contain spaces |
| Date | date | date | Parse: DD/MM/YYYY, YYYY-MM-DD, MM/DD/YYYY |

### Full column mapping (original → database)

Original CSV uses PascalCase; normalize to **lowercase snake_case** on import:

| CSV Header | DB Column | Type |
|------------|-----------|------|
| EID | eid | text |
| Date | date | date |
| Breed | breed | text |
| Treatment | treatment | text (nullable) |
| Mob | mob | text |
| Sex | sex | text |
| Weight | weight | numeric (nullable) |
| PWeight | pweight | numeric (nullable) |
| GrowthPBS | growthpbs | numeric (nullable) |
| FinalPweight | finalpweight | numeric (nullable) |
| FinalGrowthPBS | finalgrowthpbs | numeric (nullable) |
| FinalDailyGrowth | finaldailygrowth | numeric (nullable) |
| FeedIntakeKgd | feedintakekgd | numeric (nullable) |
| FeedIntakePCT | feedintakepct | numeric (nullable) |
| Methane | methane | numeric (nullable) |
| AnimalValue | animalvalue | numeric (nullable) |
| AnimalProd | animalprod | numeric (nullable) |
| FeedIntakeKgdSum | feedintakekgdsum | numeric (nullable) |
| FinalGrowthPBSSum | finalgrowthpbssum | numeric (nullable) |
| AnimalProdSum | animalprodsum | numeric (nullable) |
| MethaneSum | methanesum | numeric (nullable) |
| MethaneSupplSum | methanesupplsum | numeric (nullable) |
| CarcassWeight | carcassweight | numeric (nullable) |
| DressedCarcass | dressedcarcass | numeric (nullable) |

### Primary chart measures
Only these appear in the Measure dropdown (numeric cols used for KPIs/charts):

```python
MEASURE_CHOICES = [
    "finalpweight",
    "finalgrowthpbs",
    "methane",
    "animalvalue",
    "animalprod",
    "carcassweight",
    "feedintakekgd",
]

MEASURE_LABELS = {
    "finalpweight": "Final processed weight (kg)",
    "finalgrowthpbs": "Final growth PBS (kg/day)",
    "methane": "Methane production (g/day)",
    "animalvalue": "Animal value ($)",
    "animalprod": "Animal production rate (S/day)",
    "carcassweight": "Carcass weight (kg)",
    "feedintakekgd": "Feed intake (kg/day)",
}

MEASURE_UNITS = {
    "finalpweight": "kg",
    "finalgrowthpbs": "kg/day",
    "methane": "g/day",
    "animalvalue": "$",
    "animalprod": "units",
    "carcassweight": "kg",
    "feedintakekgd": "kg/day",
}
```

### Import rules
1. Add `farm_id` column from upload context (not in CSV)
2. `Treatment` NULL/empty → store as SQL NULL; display as "No Treatment"
3. `Sex` missing → default `"Unknown"`
4. Duplicate key `(farm_id, eid, date)`:
   - **SKIP** (default): ignore new row
   - **OVERWRITE**: replace existing row
5. After import: `ANALYZE` equivalent — refresh materialized stats if used
6. Archive uploaded file to Supabase Storage `uploads/archive/`

### Sample data stats (farm KF)
- ~12,000+ rows
- Date range: 2023–2024
- Breeds: Brahman X, etc.
- Treatments: Drench, etc.
- Mobs: Front, etc.
- Sex: Steer, etc.

Implementer should bundle a trimmed sample CSV (1000 rows) for dev; full file optional.

---

## Filter choice endpoints response shape

```json
{
  "years": [2023, 2024],
  "months": ["All", "January", "February", "..."],
  "days": ["All", 1, 2, "...", 31],
  "sexes": ["Overall", "Heifer", "Steer"],
  "treatments": ["Overall", "No Treatment", "Drench"],
  "breeds": ["Overall", "Brahman X"],
  "mobs": ["Overall", "Front"],
  "eids": ["Overall", "982 123536700233", "..."],
  "max_year": 2024,
  "measures": [
    {"key": "finalpweight", "label": "Final processed weight (kg)"}
  ],
  "total_records": 12118
}
```

`eids` array only returned when `is_admin=true`.

---

## Query request body (shared across pages)

```json
{
  "farm_id": "KF",
  "year": 2024,
  "month": "All",
  "day": "All",
  "sex": ["Overall"],
  "treatment": ["Overall"],
  "breed": ["Overall"],
  "mob": ["Overall"],
  "eid": ["Overall"],
  "measure": "finalpweight"
}
```

---

## Grouped data response row shape

```json
{
  "eid": "982 123536700493",
  "date": "2023-10-14",
  "breed": "Brahman X",
  "treatment": "Drench",
  "mob": "Front",
  "sex": "Steer",
  "finalpweight": 650.65,
  "group": "Overall Average",
  "treatment_display": "Drench"
}
```

For time series aggregation, server also returns:

```json
{
  "timeseries": [
    {
      "date": "2023-10-14",
      "group": "Sex: Steer",
      "value": 612.5,
      "count": 42
    }
  ]
}
```

---

## Cohort analysis response

```json
{
  "percentile": 10,
  "total_animals": 500,
  "top": {
    "count": 50,
    "average": 620.5,
    "min": 580.0,
    "max": 700.0,
    "animals": [{"eid": "...", "avg_measure": 680.2}]
  },
  "bottom": {
    "count": 50,
    "average": 420.1,
    "min": 380.0,
    "max": 460.0,
    "animals": [{"eid": "...", "avg_measure": 395.0}]
  },
  "show_mixed_warning": false,
  "timeline": [
    {"date": "2023-10-01", "cohort": "top", "value": 600.0}
  ]
}
```

### Cohort algorithm (must match original)
1. Filter data per sidebar filters
2. If any multi-select has both "Overall" and specific values → `show_mixed_warning: true`
3. Group by `eid`, compute `mean(measure)` across all dates
4. Rank animals by mean descending
5. `n_top = ceil(n_animals * percentile / 100)`
6. Top cohort = highest ranks; bottom = lowest ranks
7. Timeline: for animals in top/bottom, plot daily mean measure

---

## Summary stats windows

For each `full_group` in grouped data:

| Window | Definition |
|--------|------------|
| Last Day | `date == max(date)` in group |
| Last 15 Days | `date >= max(date) - 14 days` |
| Last Month | `date >= max(date) - 30 days` |
| Overall | all rows in group |

KPI per window: mean, min, max, median, count (non-null measure values).

Format currency with `$` prefix; other units suffix.

---

## Saved views (client-side)

localStorage key: `livestock_saved_views`

```json
{
  "My View": {
    "year": 2024,
    "month": "October",
    "day": "All",
    "sex": ["Steer"],
    "treatment": ["Overall"],
    "breed": ["Overall"],
    "mob": ["Overall"],
    "eid": null,
    "measure": "finalpweight",
    "timestamp": "2025-01-22T10:00:00Z"
  }
}
```

`eid` omitted for non-admin users.

---

## Email schedule `report_filters` JSON

Same shape as query request body, plus:

```json
{
  "farm_id": "KF",
  "year": 2024,
  "measure": "finalpweight",
  "report_charts": ["Distribution", "Summary Statistics"],
  "report_format": "PDF"
}
```
