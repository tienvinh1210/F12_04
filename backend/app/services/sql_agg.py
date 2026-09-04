from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta
from typing import Any

from app.constants import MEASURE_CHOICES, MEASURE_LABELS, MEASURE_UNITS, MONTH_NAMES
from app.models.schemas import FilterState
from app.services.filter_service import FilterService, friendly_label, treatment_display

ALLOWED_MEASURES = set(MEASURE_CHOICES)


def _validate_measure(measure: str) -> str:
    if measure not in ALLOWED_MEASURES:
        raise ValueError(f"Invalid measure: {measure}")
    return measure


def expand_dims_from_filters(filters: FilterState, is_admin: bool) -> dict[str, list[str]]:
    def expand(selected: list[str] | None) -> list[str]:
        selected = selected or ["Overall"]
        has_all = "Overall" in selected
        specifics = [v for v in selected if v != "Overall"]
        if has_all and not specifics:
            return ["Overall"]
        if has_all and specifics:
            return ["Overall"] + specifics
        if specifics:
            return specifics
        return ["Overall"]

    return {
        "sex": expand(filters.sex),
        "treatment": expand(filters.treatment),
        "breed": expand(filters.breed),
        "mob": expand(filters.mob),
        "eid": expand(filters.eid) if is_admin else ["Overall"],
    }


def base_where_sql(filters: FilterState, is_admin: bool) -> tuple[str, list[Any]]:
    clauses = ["farm_id = %s", "date >= %s::date", "date < %s::date"]
    params: list[Any] = [
        filters.farm_id,
        f"{filters.year}-01-01",
        f"{filters.year + 1}-01-01",
    ]

    if filters.month and filters.month != "All":
        clauses.append("EXTRACT(MONTH FROM date)::int = %s")
        params.append(MONTH_NAMES.index(filters.month))

    if filters.day and filters.day != "All":
        clauses.append("EXTRACT(DAY FROM date)::int = %s")
        params.append(int(filters.day))

    def apply_dim(col: str, selected: list[str] | None, *, allow_null_token: str | None = None) -> None:
        selected = selected or ["Overall"]
        if "Overall" in selected:
            return
        specifics = [v for v in selected if v != "Overall"]
        if not specifics:
            return
        if allow_null_token and allow_null_token in specifics:
            others = [v for v in specifics if v != allow_null_token]
            if others:
                clauses.append(f"({col} IS NULL OR {col} = ANY(%s))")
                params.append(others)
            else:
                clauses.append(f"{col} IS NULL")
        else:
            clauses.append(f"{col} = ANY(%s)")
            params.append(specifics)

    apply_dim("sex", filters.sex)
    apply_dim("treatment", filters.treatment, allow_null_token="No Treatment")
    apply_dim("breed", filters.breed)
    apply_dim("mob", filters.mob)
    if is_admin:
        apply_dim("eid", filters.eid)

    return " AND ".join(clauses), params


def _active_group_cols(dims: dict[str, list[str]]) -> list[str]:
    cols: list[str] = []
    for dim, vals in dims.items():
        if vals == ["Overall"]:
            continue
        if "Overall" in vals or len(vals) > 1:
            cols.append(dim)
    return cols


def _combo_match(row: dict, combo: dict, group_cols: list[str] | None = None) -> bool:
    """Match a grain row to a filter combo.

    Dimensions collapsed in SQL (constant via WHERE) are not re-checked against
    placeholder literals like sex='Overall'.
    """
    grouped = set(group_cols or ("sex", "treatment", "breed", "mob", "eid"))

    if combo["sex"] != "Overall" and "sex" in grouped and row["sex"] != combo["sex"]:
        return False
    if combo["treatment"] != "Overall" and "treatment" in grouped:
        treat = treatment_display(None if row["treatment"] == "__NONE__" else row["treatment"])
        if treat != combo["treatment"]:
            return False
    if combo["breed"] != "Overall" and "breed" in grouped and row["breed"] != combo["breed"]:
        return False
    if combo["mob"] != "Overall" and "mob" in grouped and row["mob"] != combo["mob"]:
        return False
    if combo["eid"] != "Overall" and "eid" in grouped and row.get("eid") != combo["eid"]:
        return False
    return True


def _as_date(val: Any) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val)[:10])


def _need_eid(filters: FilterState, is_admin: bool) -> bool:
    return is_admin and any(v != "Overall" for v in (filters.eid or ["Overall"]))


def _fetch_daily_grain(filters: FilterState, is_admin: bool, measure: str) -> list[dict]:
    from app.db import fetch_all

    measure = _validate_measure(measure)
    where, params = base_where_sql(filters, is_admin)
    dims = expand_dims_from_filters(filters, is_admin)
    group_cols = _active_group_cols(dims)

    def select_expr(col: str) -> str:
        if col in group_cols:
            if col == "treatment":
                return "COALESCE(treatment, '__NONE__') AS treatment"
            return col
        if col == "treatment":
            return "'__NONE__'::text AS treatment"
        return f"'Overall'::text AS {col}"

    select_parts = ["date"] + [select_expr(c) for c in ("sex", "treatment", "breed", "mob", "eid")]
    if group_cols:
        group_sql = ", ".join(
            ["date"]
            + ["COALESCE(treatment, '__NONE__')" if c == "treatment" else c for c in group_cols]
        )
    else:
        group_sql = "date"

    return fetch_all(
        f"""
        SELECT
          {", ".join(select_parts)},
          AVG({measure})::float AS value,
          COUNT(*)::int AS count,
          MIN({measure})::float AS min_v,
          MAX({measure})::float AS max_v
        FROM animal_data
        WHERE {where} AND {measure} IS NOT NULL
        GROUP BY {group_sql}
        ORDER BY date
        """,
        tuple(params),
    )


def _smooth_series(series: list[dict]) -> list[dict]:
    by_group: dict[str, list[dict]] = {}
    for row in series:
        by_group.setdefault(row["group"], []).append(row)
    extra: list[dict] = []
    for group, pts in by_group.items():
        pts = sorted(pts, key=lambda r: r["date"])
        if len(pts) < 3:
            continue
        window = max(3, min(15, len(pts) // 5 or 3))
        values = [p["value"] for p in pts]
        for i, p in enumerate(pts):
            lo = max(0, i - window // 2)
            hi = min(len(values), i + window // 2 + 1)
            chunk = values[lo:hi]
            extra.append(
                {
                    "date": p["date"],
                    "group": f"{group} (trend)",
                    "value": round(sum(chunk) / len(chunk), 2),
                    "count": p["count"],
                }
            )
    return series + extra


def _series_for_combos(
    grain: list[dict], filters: FilterState, is_admin: bool
) -> tuple[list[dict], dict, str | None]:
    dims = expand_dims_from_filters(filters, is_admin)
    group_cols = _active_group_cols(dims)
    combos = list(
        itertools.product(dims["sex"], dims["treatment"], dims["breed"], dims["mob"], dims["eid"])
    )
    varying = [d for d, vals in dims.items() if len(vals) > 1]
    all_overall = all(vals == ["Overall"] for vals in dims.values())

    series: list[dict] = []
    present: list[str] = []
    missing: list[str] = []

    for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
        combo = {
            "sex": sex_v,
            "treatment": treat_v,
            "breed": breed_v,
            "mob": mob_v,
            "eid": eid_v if is_admin else "Overall",
        }
        label = FilterService.label_from_combo(combo, varying, all_overall)
        buckets: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for row in grain:
            if not _combo_match(row, combo, group_cols):
                continue
            d = _as_date(row["date"]).isoformat()
            c = int(row["count"] or 0)
            v = float(row["value"])
            if d not in buckets:
                buckets[d] = [0.0, 0.0]
            buckets[d][0] += v * c
            buckets[d][1] += c
            counts[d] = counts.get(d, 0) + c

        if not buckets:
            missing.append(label)
            continue
        present.append(label)
        for d in sorted(buckets):
            total_w, total_c = buckets[d]
            series.append(
                {
                    "date": d,
                    "group": label,
                    "value": round(total_w / total_c, 2) if total_c else 0.0,
                    "count": counts[d],
                }
            )

    coverage = {
        "expected": len(combos),
        "present": len(present),
        "missing": len(missing),
        "present_groups": present,
        "missing_groups": missing,
    }
    note = None
    if len(present) > 1 and varying:
        if len(varying) == 1:
            note = f"Comparing groups by {friendly_label(varying[0])} only"
        else:
            note = f"Comparing groups by {', '.join(friendly_label(v) for v in varying)}"
    return series, coverage, note


def timeseries_sql(
    filters: FilterState, is_admin: bool, measure: str, show_smooth: bool = False
) -> dict:
    measure = _validate_measure(measure)
    grain = _fetch_daily_grain(filters, is_admin, measure)
    series, coverage, note = _series_for_combos(grain, filters, is_admin)
    if show_smooth:
        series = _smooth_series(series)

    label = MEASURE_LABELS.get(measure, measure)
    unit = MEASURE_UNITS.get(measure, "")
    return {
        "series": series,
        "y_label": f"{label} ({unit})",
        "combo_coverage": coverage,
        "common_filters_note": note,
        "record_count": sum(int(r["count"]) for r in grain),
    }


# Cache full dimensional grain so checkbox toggles can be recomputed in the browser.
_TS_GRAIN_CACHE: dict[tuple, tuple[float, dict]] = {}
_TS_GRAIN_TTL = 300.0


def _scope_where_sql(filters: FilterState) -> tuple[str, list[Any]]:
    """Year/month/day scope only — dimension filters applied client-side."""
    clauses = ["farm_id = %s", "date >= %s::date", "date < %s::date"]
    params: list[Any] = [
        filters.farm_id,
        f"{filters.year}-01-01",
        f"{filters.year + 1}-01-01",
    ]
    if filters.month and filters.month != "All":
        clauses.append("EXTRACT(MONTH FROM date)::int = %s")
        params.append(MONTH_NAMES.index(filters.month))
    if filters.day and filters.day != "All":
        clauses.append("EXTRACT(DAY FROM date)::int = %s")
        params.append(int(filters.day))
    return " AND ".join(clauses), params


def timeseries_grain_sql(filters: FilterState, measure: str) -> dict:
    """Return date×dim grain for client-side series assembly (checkbox-fast path)."""
    import time

    from app.db import fetch_all

    measure = _validate_measure(measure)
    cache_key = (
        filters.farm_id,
        filters.year,
        filters.month or "All",
        str(filters.day or "All"),
        measure,
    )
    now = time.monotonic()
    cached = _TS_GRAIN_CACHE.get(cache_key)
    if cached and now - cached[0] < _TS_GRAIN_TTL:
        return cached[1]

    where, params = _scope_where_sql(filters)
    rows = fetch_all(
        f"""
        SELECT
          to_char(date, 'YYYY-MM-DD') AS d,
          sex AS s,
          CASE WHEN treatment IS NULL THEN 'No Treatment' ELSE treatment END AS t,
          breed AS b,
          mob AS m,
          ROUND(AVG({measure})::numeric, 4)::float AS v,
          COUNT(*)::int AS c,
          MIN({measure})::float AS mn,
          MAX({measure})::float AS mx
        FROM animal_data
        WHERE {where} AND {measure} IS NOT NULL
        GROUP BY date, sex, treatment, breed, mob
        ORDER BY date
        """,
        tuple(params),
    )
    label = MEASURE_LABELS.get(measure, measure)
    unit = MEASURE_UNITS.get(measure, "")
    payload = {
        "grain": rows,
        "y_label": f"{label} ({unit})",
        "record_count": sum(int(r["c"]) for r in rows),
        "scope": {
            "farm_id": filters.farm_id,
            "year": filters.year,
            "month": filters.month or "All",
            "day": str(filters.day or "All"),
            "measure": measure,
        },
    }
    _TS_GRAIN_CACHE[cache_key] = (now, payload)
    return payload


def summary_sql(filters: FilterState, is_admin: bool, measure: str) -> dict:
    """Prefer the shared dimensional grain (same cache as timeseries) for speed."""
    measure = _validate_measure(measure)
    # Non-EID path: reuse timeseries grain cache / query, then assemble windows.
    eid_active = is_admin and any(v != "Overall" for v in (filters.eid or ["Overall"]))
    if not eid_active:
        payload = timeseries_grain_sql(filters, measure)
        # Adapt short keys to the shape _series helpers / summary expect
        grain = [
            {
                "date": r["d"],
                "sex": r["s"],
                "treatment": "__NONE__" if r["t"] == "No Treatment" else r["t"],
                "breed": r["b"],
                "mob": r["m"],
                "value": r["v"],
                "count": r["c"],
                "min_v": r.get("mn", r["v"]),
                "max_v": r.get("mx", r["v"]),
            }
            for r in payload["grain"]
        ]
        # Rebuild FilterState-style matching using full dim grain (all cols grouped)
        dims = expand_dims_from_filters(filters, is_admin)
        group_cols = ["sex", "treatment", "breed", "mob"]
        combos = list(
            itertools.product(
                dims["sex"], dims["treatment"], dims["breed"], dims["mob"], dims["eid"]
            )
        )
        all_overall = all(vals == ["Overall"] for vals in dims.values())
        unit = MEASURE_UNITS.get(measure, "")
        groups_out: list[dict] = []
        for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
            combo = {
                "sex": sex_v,
                "treatment": treat_v,
                "breed": breed_v,
                "mob": mob_v,
                "eid": eid_v if is_admin else "Overall",
            }
            matched = [r for r in grain if _combo_match(r, combo, group_cols)]
            if not matched:
                continue
            full = FilterService.full_label_from_combo(combo, is_admin)
            max_d = max(_as_date(r["date"]) for r in matched)

            def window_rows(days: int | None, matched_rows=matched, max_date=max_d) -> list[dict]:
                if days is None:
                    return matched_rows
                start = max_date - timedelta(days=days - 1)
                return [r for r in matched_rows if _as_date(r["date"]) >= start]

            def kpi(rows: list[dict], label: str) -> dict:
                if not rows:
                    return {
                        "mean": 0,
                        "min": 0,
                        "max": 0,
                        "median": 0,
                        "count": 0,
                        "unit": unit,
                        "label": label,
                    }
                daily_means: list[float] = []
                total_c = 0
                wsum = 0.0
                min_v = None
                max_v = None
                for r in rows:
                    c = int(r["count"])
                    v = float(r["value"])
                    total_c += c
                    wsum += v * c
                    daily_means.append(v)
                    mn = float(r["min_v"]) if r.get("min_v") is not None else v
                    mx = float(r["max_v"]) if r.get("max_v") is not None else v
                    min_v = mn if min_v is None else min(min_v, mn)
                    max_v = mx if max_v is None else max(max_v, mx)
                daily_means.sort()
                mid = len(daily_means) // 2
                if not daily_means:
                    med = 0.0
                elif len(daily_means) % 2:
                    med = daily_means[mid]
                else:
                    med = (daily_means[mid - 1] + daily_means[mid]) / 2
                return {
                    "mean": round(wsum / total_c, 2) if total_c else 0,
                    "min": round(min_v or 0, 2),
                    "max": round(max_v or 0, 2),
                    "median": round(med, 2),
                    "count": total_c,
                    "unit": unit,
                    "label": label,
                }

            groups_out.append(
                {
                    "full_group": full,
                    "windows": {
                        "last_day": kpi(window_rows(1), f"Last Day ({max_d.strftime('%d/%m/%Y')})"),
                        "last_15_days": kpi(window_rows(15), "Last 15 Days"),
                        "last_month": kpi(window_rows(31), "Last Month"),
                        "overall": kpi(matched, "Overall"),
                    },
                }
            )

        if len(groups_out) == 1 and all_overall:
            groups_out[0]["full_group"] = FilterService.full_label_from_combo(
                {
                    "sex": "Overall",
                    "treatment": "Overall",
                    "breed": "Overall",
                    "mob": "Overall",
                    "eid": "Overall",
                },
                is_admin,
            )
        return {"groups": groups_out, "record_count": int(payload.get("record_count") or 0)}

    # EID-aware fallback (admin): previous active-group query path
    grain = _fetch_daily_grain(filters, is_admin, measure)
    dims = expand_dims_from_filters(filters, is_admin)
    group_cols = _active_group_cols(dims)
    combos = list(
        itertools.product(dims["sex"], dims["treatment"], dims["breed"], dims["mob"], dims["eid"])
    )
    all_overall = all(vals == ["Overall"] for vals in dims.values())
    unit = MEASURE_UNITS.get(measure, "")
    groups_out = []
    total_records = sum(int(r["count"]) for r in grain)

    for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
        combo = {
            "sex": sex_v,
            "treatment": treat_v,
            "breed": breed_v,
            "mob": mob_v,
            "eid": eid_v if is_admin else "Overall",
        }
        matched = [r for r in grain if _combo_match(r, combo, group_cols)]
        if not matched:
            continue
        full = FilterService.full_label_from_combo(combo, is_admin)
        max_d = max(_as_date(r["date"]) for r in matched)

        def window_rows(days: int | None, matched_rows=matched, max_date=max_d) -> list[dict]:
            if days is None:
                return matched_rows
            start = max_date - timedelta(days=days - 1)
            return [r for r in matched_rows if _as_date(r["date"]) >= start]

        def kpi(rows: list[dict], label: str) -> dict:
            if not rows:
                return {
                    "mean": 0,
                    "min": 0,
                    "max": 0,
                    "median": 0,
                    "count": 0,
                    "unit": unit,
                    "label": label,
                }
            daily_means = []
            total_c = 0
            wsum = 0.0
            min_v = None
            max_v = None
            for r in rows:
                c = int(r["count"])
                v = float(r["value"])
                total_c += c
                wsum += v * c
                daily_means.append(v)
                mn = float(r["min_v"]) if r.get("min_v") is not None else v
                mx = float(r["max_v"]) if r.get("max_v") is not None else v
                min_v = mn if min_v is None else min(min_v, mn)
                max_v = mx if max_v is None else max(max_v, mx)
            daily_means.sort()
            mid = len(daily_means) // 2
            if not daily_means:
                med = 0.0
            elif len(daily_means) % 2:
                med = daily_means[mid]
            else:
                med = (daily_means[mid - 1] + daily_means[mid]) / 2
            return {
                "mean": round(wsum / total_c, 2) if total_c else 0,
                "min": round(min_v or 0, 2),
                "max": round(max_v or 0, 2),
                "median": round(med, 2),
                "count": total_c,
                "unit": unit,
                "label": label,
            }

        groups_out.append(
            {
                "full_group": full,
                "windows": {
                    "last_day": kpi(window_rows(1), f"Last Day ({max_d.strftime('%d/%m/%Y')})"),
                    "last_15_days": kpi(window_rows(15), "Last 15 Days"),
                    "last_month": kpi(window_rows(31), "Last Month"),
                    "overall": kpi(matched, "Overall"),
                },
            }
        )

    if len(groups_out) == 1 and all_overall:
        groups_out[0]["full_group"] = FilterService.full_label_from_combo(
            {
                "sex": "Overall",
                "treatment": "Overall",
                "breed": "Overall",
                "mob": "Overall",
                "eid": "Overall",
            },
            is_admin,
        )

    return {"groups": groups_out, "record_count": total_records}


def distribution_sql(
    filters: FilterState, is_admin: bool, measure: str, hist_bins: int = 20
) -> dict:
    from app.db import fetch_all

    measure = _validate_measure(measure)
    hist_bins = max(10, min(50, hist_bins))
    where, params = base_where_sql(filters, is_admin)
    dims = expand_dims_from_filters(filters, is_admin)
    group_cols = _active_group_cols(dims)
    combos = list(
        itertools.product(dims["sex"], dims["treatment"], dims["breed"], dims["mob"], dims["eid"])
    )
    varying = [d for d, vals in dims.items() if len(vals) > 1]
    all_overall = all(vals == ["Overall"] for vals in dims.values())
    need_eid = _need_eid(filters, is_admin)
    eid_select = ", eid" if need_eid else ""

    rows = fetch_all(
        f"""
        SELECT sex,
               COALESCE(treatment, '__NONE__') AS treatment,
               breed,
               mob
               {eid_select},
               {measure}::float AS value
        FROM animal_data
        WHERE {where} AND {measure} IS NOT NULL
        LIMIT 4000
        """,
        tuple(params),
    )

    hist_groups = []
    box_groups = []
    all_values: list[float] = []

    for sex_v, treat_v, breed_v, mob_v, eid_v in combos:
        combo = {
            "sex": sex_v,
            "treatment": treat_v,
            "breed": breed_v,
            "mob": mob_v,
            "eid": eid_v if is_admin else "Overall",
        }
        label = FilterService.label_from_combo(combo, varying, all_overall)
        # Distribution pulls raw rows with real dim values — match on all dims.
        vals = [float(r["value"]) for r in rows if _combo_match(r, combo, None)]
        if not vals:
            continue
        sample = vals if len(vals) <= 500 else vals[:: max(1, len(vals) // 500)][:500]
        hist_groups.append({"group": label, "values": sample})
        all_values.extend(sample)
        s = sorted(vals)
        n = len(s)

        def pct(p: float) -> float:
            if n == 1:
                return s[0]
            idx = p * (n - 1)
            lo = int(idx)
            hi = min(lo + 1, n - 1)
            frac = idx - lo
            return s[lo] * (1 - frac) + s[hi] * frac

        box_groups.append(
            {
                "group": label,
                "min": round(s[0], 2),
                "q1": round(pct(0.25), 2),
                "median": round(pct(0.5), 2),
                "q3": round(pct(0.75), 2),
                "max": round(s[-1], 2),
            }
        )

    mean_val = round(sum(all_values) / len(all_values), 2) if all_values else 0
    med_sorted = sorted(all_values)
    if not med_sorted:
        median_val = 0.0
    elif len(med_sorted) % 2:
        median_val = round(med_sorted[len(med_sorted) // 2], 2)
    else:
        m = len(med_sorted) // 2
        median_val = round((med_sorted[m - 1] + med_sorted[m]) / 2, 2)

    return {
        "histogram": {
            "bins": hist_bins,
            "groups": hist_groups,
            "mean": mean_val,
            "median": median_val,
        },
        "boxplot": {"groups": box_groups},
        "record_count": len(rows),
    }


def count_filtered(filters: FilterState, is_admin: bool) -> dict:
    from app.db import get_conn
    import psycopg2.extras

    where, params = base_where_sql(filters, is_admin)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT COUNT(*)::int AS record_count FROM animal_data WHERE {where}",
                tuple(params),
            )
            filtered = dict(cur.fetchone() or {})
            cur.execute(
                "SELECT COUNT(*)::int AS total_records FROM animal_data WHERE farm_id = %s",
                (filters.farm_id,),
            )
            total = dict(cur.fetchone() or {})
    return {
        "record_count": int(filtered.get("record_count") or 0),
        "total_records": int(total.get("total_records") or 0),
    }
