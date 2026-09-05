"""Filter dropdown choices — SQL only, no pandas."""
from __future__ import annotations

from app.constants import MEASURE_LABELS, MONTH_NAMES


def get_filter_choices(farm_id: str, is_admin: bool) -> dict:
    from app.db import get_conn
    import psycopg2.extras

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

    result = {
        "years": year_list,
        "months": MONTH_NAMES,
        "days": ["All"] + list(range(1, 32)),
        "sexes": ["Overall"] + sexes,
        "treatments": ["Overall", "No Treatment"] + treatments_raw,
        "breeds": ["Overall"] + breeds,
        "mobs": ["Overall"] + mobs,
        "max_year": max_year,
        "measures": [{"key": k, "label": MEASURE_LABELS[k]} for k in MEASURE_LABELS],
        "total_records": int(meta.get("cnt") or 0),
    }
    if is_admin:
        result["eids"] = ["Overall"] + eids
    return result
