from __future__ import annotations

import io
import json
import os
import re
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import CurrentUser, require_admin
from app.auth.passwords import hash_password
from app.constants import CSV_COLUMN_MAP
from app.db import execute, execute_returning, fetch_all, fetch_one
from app.models.schemas import FarmCreate, UserCreate
from app.config import get_settings

router = APIRouter()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "")
        for csv_key, db_col in {
            "eid": "eid",
            "date": "date",
            "breed": "breed",
            "treatment": "treatment",
            "mob": "mob",
            "sex": "sex",
            "weight": "weight",
            "pweight": "pweight",
            "growthpbs": "growthpbs",
            "finalpweight": "finalpweight",
            "finalgrowthpbs": "finalgrowthpbs",
            "finaldailygrowth": "finaldailygrowth",
            "feedintakekgd": "feedintakekgd",
            "feedintakepct": "feedintakepct",
            "methane": "methane",
            "animalvalue": "animalvalue",
            "animalprod": "animalprod",
            "feedintakekgdsum": "feedintakekgdsum",
            "finalgrowthpbssum": "finalgrowthpbssum",
            "animalprodsum": "animalprodsum",
            "methanesum": "methanesum",
            "methanesupplsum": "methanesupplsum",
            "carcassweight": "carcassweight",
            "dressedcarcass": "dressedcarcass",
        }.items():
            if key == csv_key or col.strip().lower() == csv_key:
                col_map[col] = db_col
    return df.rename(columns=col_map)


@router.post("/farms")
def create_farm(body: FarmCreate, user: Annotated[CurrentUser, Depends(require_admin)]):
    execute(
        "INSERT INTO farms (farm_id, farm_name, slug) VALUES (%s, %s, %s)",
        (body.farm_id, body.farm_name, body.slug),
    )
    return {"detail": "Farm created", "farm_id": body.farm_id}


@router.post("/farms/{farm_id}/upload")
async def upload_csv(
    farm_id: str,
    user: Annotated[CurrentUser, Depends(require_admin)],
    file: UploadFile = File(...),
    duplicate_mode: str = Form("skip"),
):
    if not re.match(rf"^{re.escape(farm_id)}_.+\.csv$", file.filename or "", re.I):
        raise HTTPException(status_code=400, detail=f"Filename must match {farm_id}_YYYY-MM-DD.csv")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    df = pd.read_csv(io.BytesIO(content))
    df = _normalize_columns(df)
    if "eid" not in df.columns or "date" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain EID and Date columns")

    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["eid", "date"])
    if "sex" not in df.columns:
        df["sex"] = "Unknown"
    if "treatment" not in df.columns:
        df["treatment"] = None
    else:
        df["treatment"] = df["treatment"].replace("", None)

    count_row = fetch_one("SELECT COUNT(*) AS cnt FROM animal_data WHERE farm_id = %s", (farm_id,))
    snapshot = execute_returning(
        """
        INSERT INTO animal_data_snapshots (farm_id, snapshot_name, record_count, created_by)
        VALUES (%s, %s, %s, %s) RETURNING id
        """,
        (farm_id, f"pre_upload_{file.filename}", count_row["cnt"] if count_row else 0, user.username),
    )

    inserted = skipped = overwritten = 0
    numeric_cols = [c for c in CSV_COLUMN_MAP.values() if c not in ("eid", "date", "breed", "treatment", "mob", "sex")]

    for _, row in df.iterrows():
        existing = fetch_one(
            "SELECT id FROM animal_data WHERE farm_id = %s AND eid = %s AND date = %s",
            (farm_id, str(row["eid"]), row["date"].date()),
        )
        if existing:
            if duplicate_mode == "overwrite":
                sets = ", ".join(f"{c} = %s" for c in numeric_cols if c in row.index)
                vals = [row[c] if c in row.index and pd.notna(row[c]) else None for c in numeric_cols if c in row.index]
                execute(
                    f"UPDATE animal_data SET breed=%s, treatment=%s, mob=%s, sex=%s, {sets} WHERE id=%s",
                    (
                        row.get("breed"),
                        row.get("treatment"),
                        row.get("mob"),
                        row.get("sex", "Unknown"),
                        *vals,
                        existing["id"],
                    ),
                )
                overwritten += 1
            else:
                skipped += 1
            continue

        cols = ["farm_id", "eid", "date", "breed", "treatment", "mob", "sex"] + [
            c for c in numeric_cols if c in row.index
        ]
        placeholders = ", ".join(["%s"] * len(cols))
        vals = [farm_id, str(row["eid"]), row["date"].date()]
        for c in ["breed", "treatment", "mob", "sex"]:
            vals.append(row.get(c) if c != "sex" else row.get(c, "Unknown"))
        for c in numeric_cols:
            if c in row.index:
                vals.append(row[c] if pd.notna(row[c]) else None)
        execute(f"INSERT INTO animal_data ({', '.join(cols)}) VALUES ({placeholders})", tuple(vals))
        inserted += 1

    execute(
        """
        INSERT INTO data_uploads (farm_id, filename, rows_inserted, rows_skipped, rows_overwritten, duplicate_mode, uploaded_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (farm_id, file.filename, inserted, skipped, overwritten, duplicate_mode, user.username),
    )

    return {
        "rows_inserted": inserted,
        "rows_skipped": skipped,
        "rows_overwritten": overwritten,
        "snapshot_id": snapshot["id"] if snapshot else None,
    }


@router.get("/farms/{farm_id}/status")
def farm_status(farm_id: str, user: Annotated[CurrentUser, Depends(require_admin)]):
    count = fetch_one("SELECT COUNT(*) AS cnt FROM animal_data WHERE farm_id = %s", (farm_id,))
    last_upload = fetch_one(
        "SELECT created_at FROM data_uploads WHERE farm_id = %s ORDER BY created_at DESC LIMIT 1",
        (farm_id,),
    )
    snapshots = fetch_one(
        "SELECT COUNT(*) AS cnt FROM animal_data_snapshots WHERE farm_id = %s", (farm_id,)
    )
    return {
        "record_count": count["cnt"] if count else 0,
        "last_upload": last_upload["created_at"].isoformat() if last_upload and last_upload.get("created_at") else None,
        "snapshots_count": snapshots["cnt"] if snapshots else 0,
        "pending_uploads": [],
    }


@router.get("/users")
def list_users(user: Annotated[CurrentUser, Depends(require_admin)]):
    return fetch_all("SELECT id, username, is_admin, is_active, created_at FROM users ORDER BY id")


@router.post("/users")
def create_user(body: UserCreate, user: Annotated[CurrentUser, Depends(require_admin)]):
    row = execute_returning(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id, username, is_admin",
        (body.username, hash_password(body.password), body.is_admin),
    )
    for fid in body.farm_ids:
        execute("INSERT INTO user_farm_access (user_id, farm_id) VALUES (%s, %s)", (row["id"], fid))
    return row
