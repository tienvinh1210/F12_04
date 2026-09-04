from __future__ import annotations

import json
from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.auth.dependencies import CurrentUser, assert_farm_access, get_current_user
from app.config import get_settings
from app.db import execute, execute_returning, fetch_all, fetch_one
from app.models.schemas import EmailScheduleCreate, EmailSendNow, FilterState, SchedulePatch
from app.services.data_service import DataService
from app.services.email_service import EmailService, compute_next_send

router = APIRouter()


def _serialize_schedule(row: dict) -> dict:
    out = dict(row)
    for key in ("send_time", "send_date", "next_send_at", "last_sent", "created_at"):
        if out.get(key) is not None and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out


@router.get("/schedules")
def list_schedules(farm_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, farm_id)
    rows = fetch_all(
        "SELECT * FROM email_schedules WHERE farm_id = %s ORDER BY created_at DESC",
        (farm_id,),
    )
    return [_serialize_schedule(r) for r in rows]


@router.post("/schedules")
def create_schedule(body: EmailScheduleCreate, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    sched_dict = body.model_dump()
    next_at = compute_next_send(sched_dict)
    row = execute_returning(
        """
        INSERT INTO email_schedules (
            farm_id, recipient_email, schedule_name, frequency, send_time,
            send_date, day_of_week, day_of_month, next_send_at, email_subject,
            email_body, report_filters, report_charts, report_format, created_by
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            body.farm_id,
            body.recipient_email,
            body.schedule_name,
            body.frequency,
            body.send_time,
            body.send_date,
            body.day_of_week,
            body.day_of_month,
            next_at,
            body.email_subject,
            body.email_body,
            json.dumps(body.report_filters) if body.report_filters else None,
            body.report_charts,
            body.report_format,
            user.username,
        ),
    )
    return _serialize_schedule(row)


@router.post("/send-now")
def send_now(body: EmailSendNow, user: Annotated[CurrentUser, Depends(get_current_user)]):
    assert_farm_access(user, body.farm_id)
    if not (body.recipient_email or "").strip() or "@" not in body.recipient_email:
        raise HTTPException(status_code=400, detail="Enter a valid recipient email")

    farm = fetch_one("SELECT farm_name FROM farms WHERE farm_id = %s", (body.farm_id,))
    farm_name = farm["farm_name"] if farm else body.farm_id

    filters_data = dict(body.report_filters or {})
    filters_data.setdefault("farm_id", body.farm_id)
    if not filters_data.get("year"):
        filters_data["year"] = date.today().year
    # Coerce common UI shapes
    if "day" in filters_data and filters_data["day"] is None:
        filters_data["day"] = "All"
    try:
        filters = FilterState(**filters_data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid report filters: {exc}") from exc

    try:
        filtered, grouped, _, _ = DataService.get_filtered_data(filters, user.is_admin)
        from app.services.report_generator import ReportGenerator

        charts = body.report_charts or ["Summary Statistics", "Distribution"]
        pdf = ReportGenerator.generate_pdf(
            filters, grouped, charts, farm_name, filtered_df=filtered
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build report PDF: {exc}") from exc

    subject = body.email_subject or f"Automated Livestock Report - {farm_name}"
    html = EmailService.build_email_body(filters_data, body.email_body or "", farm_name)
    ok, status = EmailService.send_report_email(body.recipient_email, subject, html, pdf)
    if not ok:
        raise HTTPException(status_code=500, detail=status or "Failed to send email")
    if status == "dry_run":
        return {
            "detail": "Email dry-run only (not sent). Set EMAIL_DRY_RUN=false in Vercel env to send for real.",
            "dry_run": True,
        }
    return {"detail": "Email sent", "dry_run": False}


@router.patch("/schedules/{schedule_id}")
def patch_schedule(
    schedule_id: int,
    body: SchedulePatch,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    sched = fetch_one("SELECT * FROM email_schedules WHERE id = %s", (schedule_id,))
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    assert_farm_access(user, sched["farm_id"])
    if body.is_active is not None:
        execute("UPDATE email_schedules SET is_active = %s WHERE id = %s", (body.is_active, schedule_id))
    return {"detail": "Updated"}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: Annotated[CurrentUser, Depends(get_current_user)]):
    sched = fetch_one("SELECT * FROM email_schedules WHERE id = %s", (schedule_id,))
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    assert_farm_access(user, sched["farm_id"])
    execute("DELETE FROM email_schedules WHERE id = %s", (schedule_id,))
    return {"detail": "Deleted"}


@router.post("/process-due")
def process_due(
    x_cron_secret: str = Header(None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(None, alias="x-vercel-cron"),
    cron_secret: str | None = None,
):
    """Process due email schedules.

    Auth (any one):
    - X-Cron-Secret / ?cron_secret= matching CRON_SECRET
    - x-vercel-cron: 1 (sent automatically by Vercel Cron on Hobby/Pro)
    """
    settings = get_settings()
    secret = x_cron_secret or cron_secret
    allowed = (secret and secret == settings.cron_secret) or (x_vercel_cron == "1")
    if not allowed:
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    return EmailService.process_due_emails()
