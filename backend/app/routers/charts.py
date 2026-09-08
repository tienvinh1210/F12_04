from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.models.schemas import DistributionRequest, TimeseriesRequest
from app.services import sql_agg

router = APIRouter()


@router.post("/timeseries")
def timeseries(body: TimeseriesRequest, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    try:
        return sql_agg.timeseries_sql(body, user.is_admin, body.measure, body.show_smooth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/timeseries-grain")
def timeseries_grain(body: TimeseriesRequest, user: Annotated[CurrentUser, Depends(get_current_user)]):
    """Dimensional daily grain for client-side chart assembly (sub-second checkbox updates)."""
    assert_farm_access(user, body.farm_id)
    try:
        return sql_agg.timeseries_grain_sql(body, body.measure)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/distribution")
def distribution(body: DistributionRequest, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    try:
        return sql_agg.distribution_sql(body, user.is_admin, body.measure, body.hist_bins)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
