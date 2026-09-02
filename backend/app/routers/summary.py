from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.models.schemas import FilterState
from app.services.data_service import DataService
from app.services.summary_service import SummaryService

router = APIRouter()


@router.post("/stats")
def summary_stats(body: FilterState, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    _, grouped, _, _ = DataService.get_filtered_data(body, user.is_admin)
    return {"groups": SummaryService.compute_stats(grouped, body.measure)}
