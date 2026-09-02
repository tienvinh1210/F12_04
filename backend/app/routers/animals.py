from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.models.schemas import DataQueryRequest, FilterState
from app.services.data_service import DataService
from app.services.filter_service import FilterService
from app.utils.anonymize import anonymize_records

router = APIRouter()


def _query_response(body: DataQueryRequest, user: CurrentUser) -> dict:
    assert_farm_access(user, body.farm_id)
    filtered, grouped, _, total_records = DataService.get_filtered_data(body, user.is_admin)
    note = DataService.get_common_note(body, grouped)
    record_count = len(filtered)

    result = {
        "record_count": record_count,
        "total_records": total_records,
        "common_filters_note": note,
    }

    if body.include_rows:
        processed = grouped.copy() if not grouped.empty else filtered.copy()
        filtered_records = FilterService.df_to_records(filtered)
        processed_records = FilterService.df_to_records(processed)

        if body.page and body.page_size:
            start = (body.page - 1) * body.page_size
            end = start + body.page_size
            filtered_records = filtered_records[start:end]

        result["filtered"] = anonymize_records(filtered_records, user.is_admin)
        result["processed"] = anonymize_records(processed_records, user.is_admin)
        result["grouped"] = anonymize_records(processed_records, user.is_admin)
    else:
        result["filtered"] = []
        result["processed"] = []
        result["grouped"] = []

    return result


@router.post("/query")
def data_query(body: DataQueryRequest, user: Annotated[CurrentUser, Depends(get_current_user)]):
    return _query_response(body, user)


@router.get("/export.csv")
def export_csv(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    farm_id: str = Query(...),
    year: int = Query(...),
    month: str = Query("All"),
    day: str = Query("All"),
    sex: str = Query("Overall"),
    treatment: str = Query("Overall"),
    breed: str = Query("Overall"),
    mob: str = Query("Overall"),
    eid: str = Query("Overall"),
):
    assert_farm_access(user, farm_id)
    if not user.is_admin and eid != "Overall":
        raise HTTPException(status_code=403, detail="EID filter requires admin access")

    def split_multi(val: str) -> list[str]:
        return [v.strip() for v in val.split("|") if v.strip()]

    filters = FilterState(
        farm_id=farm_id,
        year=year,
        month=month,
        day=day if day != "All" else "All",
        sex=split_multi(sex),
        treatment=split_multi(treatment),
        breed=split_multi(breed),
        mob=split_multi(mob),
        eid=split_multi(eid),
    )
    filtered, _, _, _ = DataService.get_filtered_data(filters, user.is_admin)
    records = FilterService.df_to_records(filtered)
    records = anonymize_records(records, user.is_admin)

    output = io.StringIO()
    if records:
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    else:
        output.write("No data\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{farm_id}_export.csv"'},
    )
