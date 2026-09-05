from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.services.choices_service import get_filter_choices

router = APIRouter()


@router.get("/choices")
def filter_choices(
    farm_id: str = Query(...),
    user: Annotated[CurrentUser, Depends(get_current_user)] = None,
):
    assert_farm_access(user, farm_id)
    return get_filter_choices(farm_id, user.is_admin)
