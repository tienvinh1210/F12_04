from __future__ import annotations

import itertools
import time
from typing import Any

import pandas as pd

from app.constants import MEASURE_LABELS, MEASURE_UNITS, MONTH_NAMES
from app.models.schemas import FilterState

# Warm serverless instances keep this across requests — avoids re-pulling ~12k rows
# from Supabase on every chart/summary call.
_FARM_DF_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_FARM_DF_TTL_SEC = 180


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


def treatment_display(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "No Treatment"
    return str(val)


class FilterService:
    @staticmethod
    def load_farm_dataframe(farm_id: str, *, use_cache: bool = True) -> pd.DataFrame:
        from app.db import fetch_all

        now = time.monotonic()
        if use_cache and farm_id in _FARM_DF_CACHE:
            cached_at, cached_df = _FARM_DF_CACHE[farm_id]
            if now - cached_at < _FARM_DF_TTL_SEC:
                return cached_df

        rows = fetch_all(
            """
            SELECT eid, date, breed, treatment, mob, sex, weight, pweight, growthpbs,
                   finalpweight, finalgrowthpbs, finaldailygrowth, feedintakekgd, feedintakepct,
                   methane, animalvalue, animalprod, feedintakekgdsum, finalgrowthpbssum,
                   animalprodsum, methanesum, methanesupplsum, carcassweight, dressedcarcass
            FROM animal_data WHERE farm_id = %s
            """,
            (farm_id,),
        )
        if not rows:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
        if use_cache:
            _FARM_DF_CACHE[farm_id] = (now, df)
        return df

    @staticmethod
    def filter_data(df: pd.DataFrame, filters: FilterState, is_admin: bool) -> pd.DataFrame:
        if filters.year is None:
            raise ValueError("Year is required")
        if df.empty:
            return df

        out = df[df["date"].dt.year == filters.year].copy()

        if filters.month and filters.month != "All":
            month_num = MONTH_NAMES.index(filters.month)
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

    @staticmethod
    def _expand_dimension(selected: list[str], unique_values: list[str]) -> list[str]:
        selected = selected or ["Overall"]
        has_all = "Overall" in selected
        specifics = [v for v in selected if v != "Overall"]
        if has_all and not specifics:
            return ["Overall"]
        if has_all and specifics:
            return ["Overall"] + specifics
        if specifics:
            # One or more specific values selected (no Overall)
            return specifics
        return unique_values if unique_values else ["Overall"]

    @staticmethod
    def expand_filter_dimensions(
        base_df: pd.DataFrame, filters: FilterState, is_admin: bool
    ) -> dict[str, list[str]]:
        def unique_treatments(df: pd.DataFrame) -> list[str]:
            return sorted({treatment_display(t) for t in df["treatment"].unique()}) or ["No Treatment"]

        return {
            "sex": FilterService._expand_dimension(
                filters.sex, sorted(base_df["sex"].dropna().unique().tolist())
            ),
            "treatment": FilterService._expand_dimension(
                filters.treatment, unique_treatments(base_df)
            ),
            "breed": FilterService._expand_dimension(
                filters.breed, sorted(base_df["breed"].dropna().unique().tolist())
            ),
            "mob": FilterService._expand_dimension(
                filters.mob, sorted(base_df["mob"].dropna().unique().tolist())
            ),
            "eid": (
                FilterService._expand_dimension(
                    filters.eid, sorted(base_df["eid"].dropna().unique().tolist())
                )
                if is_admin
                else ["Overall"]
            ),
        }

    @staticmethod
    def combo_coverage(
        base_df: pd.DataFrame, filters: FilterState, is_admin: bool
    ) -> dict:
        """Report how many filter combinations exist vs are empty in the data."""
        if base_df.empty:
            return {
                "expected": 0,
                "present": 0,
                "missing": 0,
                "present_groups": [],
                "missing_groups": [],
            }

        dims = FilterService.expand_filter_dimensions(base_df, filters, is_admin)
        varying_dims = [d for d, vals in dims.items() if len(vals) > 1]
        all_overall = all(vals == ["Overall"] for vals in dims.values())
        combos = list(
            itertools.product(
                dims["sex"], dims["treatment"], dims["breed"], dims["mob"], dims["eid"]
            )
        )

        present_groups: list[str] = []
        missing_groups: list[str] = []
        for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
            subset = base_df
            if sex_v != "Overall":
                subset = subset[subset["sex"] == sex_v]
            if treat_v != "Overall":
                if treat_v == "No Treatment":
                    subset = subset[subset["treatment"].isna()]
                else:
                    subset = subset[subset["treatment"] == treat_v]
            if breed_v != "Overall":
                subset = subset[subset["breed"] == breed_v]
            if mob_v != "Overall":
                subset = subset[subset["mob"] == mob_v]
            if eid_v != "Overall":
                subset = subset[subset["eid"] == eid_v]

            combo = {
                "sex": sex_v,
                "treatment": treat_v,
                "breed": breed_v,
                "mob": mob_v,
                "eid": eid_v if is_admin else "Overall",
            }
            label = FilterService.label_from_combo(combo, varying_dims, all_overall)
            if subset.empty:
                missing_groups.append(label)
            else:
                present_groups.append(label)

        return {
            "expected": len(combos),
            "present": len(present_groups),
            "missing": len(missing_groups),
            "present_groups": present_groups,
            "missing_groups": missing_groups,
        }

    @staticmethod
    def build_grouped_data(
        base_df: pd.DataFrame, filters: FilterState, is_admin: bool
    ) -> pd.DataFrame:
        if base_df.empty:
            return base_df.copy()

        dims = FilterService.expand_filter_dimensions(base_df, filters, is_admin)
        sex_vals = dims["sex"]
        treatment_vals = dims["treatment"]
        breed_vals = dims["breed"]
        mob_vals = dims["mob"]
        eid_vals = dims["eid"]

        combo_dims = {
            "sex": sex_vals,
            "treatment": treatment_vals,
            "breed": breed_vals,
            "mob": mob_vals,
            "eid": eid_vals,
        }
        varying_dims = [d for d, vals in combo_dims.items() if len(vals) > 1]
        all_overall = all(vals == ["Overall"] for vals in combo_dims.values())

        # Fast path: single Overall group — no combo explosion / repeated copies.
        if all_overall:
            out = base_df.copy()
            out["treatment_display"] = out["treatment"].apply(treatment_display)
            combo = {
                "sex": "Overall",
                "treatment": "Overall",
                "breed": "Overall",
                "mob": "Overall",
                "eid": "Overall",
            }
            out["group"] = FilterService.label_from_combo(combo, varying_dims, all_overall)
            out["full_group"] = FilterService.full_label_from_combo(combo, is_admin)
            return out

        combos = list(itertools.product(sex_vals, treatment_vals, breed_vals, mob_vals, eid_vals))
        parts: list[pd.DataFrame] = []

        for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
            subset = base_df
            if sex_v != "Overall":
                subset = subset[subset["sex"] == sex_v]
            if treat_v != "Overall":
                if treat_v == "No Treatment":
                    subset = subset[subset["treatment"].isna()]
                else:
                    subset = subset[subset["treatment"] == treat_v]
            if breed_v != "Overall":
                subset = subset[subset["breed"] == breed_v]
            if mob_v != "Overall":
                subset = subset[subset["mob"] == mob_v]
            if eid_v != "Overall":
                subset = subset[subset["eid"] == eid_v]
            if subset.empty:
                continue
            subset = subset.copy()
            subset["treatment_display"] = subset["treatment"].apply(treatment_display)
            combo = {
                "sex": sex_v,
                "treatment": treat_v,
                "breed": breed_v,
                "mob": mob_v,
                "eid": eid_v if is_admin else "Overall",
            }
            subset["group"] = FilterService.label_from_combo(combo, varying_dims, all_overall)
            subset["full_group"] = FilterService.full_label_from_combo(combo, is_admin)
            parts.append(subset)

        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True)

    @staticmethod
    def label_from_combo(combo: dict, varying_dims: list[str], all_overall: bool) -> str:
        if all_overall or not varying_dims:
            if all(v == "Overall" for v in combo.values()):
                return "Overall Average"
            # Single combo with some specific filter — show non-Overall dims
            parts = [
                f"{friendly_label(d)}: {combo[d]}"
                for d in ("sex", "treatment", "breed", "mob", "eid")
                if combo.get(d) and combo[d] != "Overall"
            ]
            return " | ".join(parts) if parts else "Overall Average"
        return " | ".join(f"{friendly_label(d)}: {combo[d]}" for d in varying_dims)

    @staticmethod
    def full_label_from_combo(combo: dict, is_admin: bool) -> str:
        parts = []
        for col in ("sex", "treatment", "breed", "mob"):
            parts.append(f"{friendly_label(col)}: {combo.get(col, 'Overall')}")
        eid = combo.get("eid", "Overall") if is_admin else "*****"
        parts.append(f"EID: {eid}")
        return ", ".join(parts)

    @staticmethod
    def create_simplified_group_labels(
        df: pd.DataFrame, filters: FilterState, is_admin: bool
    ) -> str:
        dims = []
        for col, selected in [
            ("sex", filters.sex),
            ("treatment", filters.treatment),
            ("breed", filters.breed),
            ("mob", filters.mob),
            ("eid", filters.eid if is_admin else ["Overall"]),
        ]:
            if col == "treatment":
                vals = [treatment_display(v) for v in df["treatment"].unique()]
            elif col == "eid":
                vals = df["eid"].unique().tolist()
            else:
                vals = df[col].dropna().unique().tolist()
            dims.append((col, vals, selected))

        all_overall = all(
            len(v) == 1 and (col != "treatment" or v[0] in ("Overall", "No Treatment"))
            for col, v, sel in dims
            if col != "eid" or is_admin
        )
        unique_combos = len(df.groupby([c for c, _, _ in dims if c in df.columns], dropna=False))

        if unique_combos <= 1:
            varying = []
            for col, vals, sel in dims:
                if col == "eid" and not is_admin:
                    continue
                if "Overall" not in sel and len(sel) > 1:
                    varying.append(col)
                elif len(vals) == 1 and vals[0] != "Overall":
                    label_val = vals[0]
                    if col == "treatment":
                        label_val = treatment_display(vals[0])
                    varying.append(f"{friendly_label(col)}: {label_val}")
            if not varying or (len(varying) == 1 and varying[0] == "Overall Average"):
                return "Overall Average"
            if all(":" in v for v in varying):
                return " | ".join(varying)
            return FilterService._build_varying_label(df, dims, is_admin)

        return FilterService._build_varying_label(df, dims, is_admin)

    @staticmethod
    def _build_varying_label(dims_data: pd.DataFrame, dims: list, is_admin: bool) -> str:
        varying_cols = []
        for col, vals, sel in dims:
            if col == "eid" and not is_admin:
                continue
            nunique = dims_data[col].nunique() if col in dims_data.columns else 1
            if col == "treatment":
                nunique = dims_data["treatment"].apply(treatment_display).nunique()
            if nunique > 1:
                varying_cols.append(col)

        if not varying_cols:
            row = dims_data.iloc[0]
            parts = []
            for col, _, _ in dims:
                if col == "eid" and not is_admin:
                    continue
                val = row.get(col)
                if col == "treatment":
                    val = treatment_display(val)
                parts.append(f"{friendly_label(col)}: {val}")
            return ", ".join(parts)

        row = dims_data.iloc[0]
        parts = []
        for col in varying_cols:
            val = row.get(col)
            if col == "treatment":
                val = treatment_display(val)
            parts.append(f"{friendly_label(col)}: {val}")
        return " | ".join(parts)

    @staticmethod
    def create_full_group_labels(df: pd.DataFrame, is_admin: bool) -> str:
        row = df.iloc[0]
        parts = []
        for col in ["sex", "treatment", "breed", "mob"]:
            val = row.get(col)
            if col == "treatment":
                val = treatment_display(val)
            parts.append(f"{friendly_label(col)}: {val}")
        if is_admin:
            parts.append(f"EID: {row.get('eid', '*****')}")
        else:
            parts.append("EID: *****")
        return ", ".join(parts)

    @staticmethod
    def get_common_filters_note(filters: FilterState, grouped_df: pd.DataFrame) -> str | None:
        varying = []
        for col, selected in [
            ("sex", filters.sex),
            ("treatment", filters.treatment),
            ("breed", filters.breed),
            ("mob", filters.mob),
        ]:
            has_all = "Overall" in selected
            has_specific = any(v != "Overall" for v in selected)
            if has_all and has_specific:
                varying.append(friendly_label(col))
            elif not has_all and len(selected) > 1:
                varying.append(friendly_label(col))

        if grouped_df.empty:
            return None
        if len(grouped_df["group"].unique()) <= 1:
            return None
        if varying:
            if len(varying) == 1:
                return f"Comparing groups by {varying[0]} only"
            return f"Comparing groups by {', '.join(varying)}"
        groups = grouped_df["group"].unique()
        if len(groups) > 1:
            return "Comparing multiple animal groups"
        return None

    @staticmethod
    def has_mixed_selection(filters: FilterState) -> bool:
        for selected in [filters.sex, filters.treatment, filters.breed, filters.mob, filters.eid]:
            if "Overall" in selected and any(v != "Overall" for v in selected):
                return True
        return False

    @staticmethod
    def get_filter_choices(farm_id: str, is_admin: bool) -> dict:
        from app.db import get_conn
        import psycopg2.extras

        # One connection + two queries instead of ~8 round-trips.
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                      COUNT(*)::int AS cnt,
                      ARRAY(
                        SELECT DISTINCT EXTRACT(YEAR FROM date)::int
                        FROM animal_data
                        WHERE farm_id = %s
                        ORDER BY 1 DESC
                      ) AS years
                    FROM animal_data
                    WHERE farm_id = %s
                    """,
                    (farm_id, farm_id),
                )
                meta = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    SELECT
                      ARRAY(SELECT DISTINCT sex FROM animal_data WHERE farm_id = %s AND sex IS NOT NULL ORDER BY 1) AS sexes,
                      ARRAY(SELECT DISTINCT treatment FROM animal_data WHERE farm_id = %s AND treatment IS NOT NULL ORDER BY 1) AS treatments,
                      ARRAY(SELECT DISTINCT breed FROM animal_data WHERE farm_id = %s AND breed IS NOT NULL ORDER BY 1) AS breeds,
                      ARRAY(SELECT DISTINCT mob FROM animal_data WHERE farm_id = %s AND mob IS NOT NULL ORDER BY 1) AS mobs,
                      ARRAY(SELECT DISTINCT eid FROM animal_data WHERE farm_id = %s AND eid IS NOT NULL ORDER BY 1) AS eids
                    """,
                    (farm_id, farm_id, farm_id, farm_id, farm_id),
                )
                dims = dict(cur.fetchone() or {})

        year_list = list(meta.get("years") or [])
        max_year = year_list[0] if year_list else None
        sexes = list(dims.get("sexes") or [])
        treatments_raw = [t for t in (dims.get("treatments") or []) if t]
        breeds = list(dims.get("breeds") or [])
        mobs = list(dims.get("mobs") or [])
        eids = list(dims.get("eids") or [])

        treatments = ["Overall", "No Treatment"] + treatments_raw
        result = {
            "years": year_list,
            "months": MONTH_NAMES,
            "days": ["All"] + list(range(1, 32)),
            "sexes": ["Overall"] + sexes,
            "treatments": treatments,
            "breeds": ["Overall"] + breeds,
            "mobs": ["Overall"] + mobs,
            "max_year": max_year,
            "measures": [
                {"key": k, "label": MEASURE_LABELS[k]} for k in MEASURE_LABELS
            ],
            "total_records": int(meta.get("cnt") or 0),
        }
        if is_admin:
            result["eids"] = ["Overall"] + eids
        return result

    @staticmethod
    def df_to_records(df: pd.DataFrame) -> list[dict]:
        if df.empty:
            return []
        out = df.copy()
        if "date" in out.columns:
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out = out.where(pd.notnull(out), None)
        return out.to_dict(orient="records")
