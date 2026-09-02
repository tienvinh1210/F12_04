from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.services.filter_service import FilterService

router = APIRouter()


@router.get("/choices")
def filter_choices(
    farm_id: str = Query(...),
    user: Annotated[CurrentUser, Depends(get_current_user)] = None,
):
    assert_farm_access(user, farm_id)
    return FilterService.get_filter_choices(farm_id, user.is_admin)
