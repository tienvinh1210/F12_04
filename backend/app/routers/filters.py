from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.models.schemas import FilterState
from app.services import sql_agg
from app.services.choices_service import get_filter_choices

router = APIRouter()


@router.get("/choices")
def filter_choices(
    farm_id: str = Query(...),
    user: Annotated[CurrentUser, Depends(get_current_user)] = None,
):
    assert_farm_access(user, farm_id)
    return get_filter_choices(farm_id, user.is_admin)


@router.get("/bootstrap")
def filter_bootstrap(
    farm_id: str = Query(...),
    measure: str = Query("finalpweight"),
    user: Annotated[CurrentUser, Depends(get_current_user)] = None,
):
    """One round-trip for dashboard first paint: choices + year grain."""
    assert_farm_access(user, farm_id)
    choices = get_filter_choices(farm_id, user.is_admin)
    year = choices.get("max_year") or (choices.get("years") or [None])[0]
    grain = None
    grain_key = None
    if year:
        filters = FilterState(
            farm_id=farm_id,
            year=int(year),
            month="All",
            day="All",
            sex=["Overall"],
            treatment=["Overall"],
            breed=["Overall"],
            mob=["Overall"],
            eid=["Overall"],
            measure=measure,
        )
        grain = sql_agg.timeseries_grain_sql(filters, measure)
        grain_key = f"{farm_id}|{year}|{measure}"
    return {"choices": choices, "grain": grain, "grain_key": grain_key}
