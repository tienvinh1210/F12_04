from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.models.schemas import CohortRequest, FilterState
from app.services.chart_service import CohortService
from app.services.data_service import DataService
from app.utils.anonymize import anonymize_records

router = APIRouter()


@router.post("/analyze")
def analyze_cohorts(body: CohortRequest, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    filtered, grouped, _, _ = DataService.get_filtered_data(body, user.is_admin)
    result = CohortService.analyze(filtered, grouped, body.measure, body.percentile, body)
    result["top"]["animals"] = anonymize_records(result["top"]["animals"], user.is_admin)
    result["bottom"]["animals"] = anonymize_records(result["bottom"]["animals"], user.is_admin)
    return result


@router.get("/export.csv")
def export_cohort(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    cohort: str = Query(...),
    farm_id: str = Query(...),
    year: int = Query(...),
    measure: str = Query("finalpweight"),
    percentile: int = Query(10),
):
    filters = FilterState(farm_id=farm_id, year=year, measure=measure)
    assert_farm_access(user, farm_id)
    filtered, grouped, _, _ = DataService.get_filtered_data(filters, user.is_admin)
    result = CohortService.analyze(filtered, grouped, measure, percentile, filters)
    animals = result["top"]["animals"] if cohort == "top" else result["bottom"]["animals"]
    animals = anonymize_records(animals, user.is_admin)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["eid", "avg_measure"])
    writer.writeheader()
    writer.writerows(animals)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="cohort_{cohort}.csv"'},
    )
