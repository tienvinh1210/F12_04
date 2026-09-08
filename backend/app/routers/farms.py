from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.config import get_settings
from app.db import fetch_all, fetch_one

router = APIRouter()


@router.get("")
def list_farms(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return fetch_all(
        """
        SELECT f.farm_id, f.farm_name, f.slug, f.is_active
        FROM farms f
        JOIN user_farm_access ufa ON ufa.farm_id = f.farm_id
        WHERE ufa.user_id = %s AND f.is_active = TRUE
        ORDER BY f.farm_name
        """,
        (user.id,),
    )


@router.get("/{farm_id}")
def get_farm(farm_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, farm_id)
    farm = fetch_one("SELECT * FROM farms WHERE farm_id = %s", (farm_id,))
    logos = _get_logos(farm_id)
    return {**farm, "logos": logos}


@router.get("/{farm_id}/logos")
def get_logos(farm_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, farm_id)
    return {"logos": _get_logos(farm_id)}


def _get_logos(farm_id: str) -> list[dict]:
    settings = get_settings()
    logos = []
    logo_dir = os.path.join(str(settings.logos_path), farm_id)
    if os.path.isdir(logo_dir):
        for fname in sorted(os.listdir(logo_dir)):
            if fname.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                logos.append({"filename": fname, "url": f"/assets/logos/{farm_id}/{fname}"})
    if not logos:
        logos.append({"filename": "default.svg", "url": "/assets/logos/default.svg"})
    return logos
