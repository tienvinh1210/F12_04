from __future__ import annotations

import base64
import io
import os
import tempfile
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.constants import MEASURE_LABELS
from app.models.schemas import FilterState

TZ = ZoneInfo("Australia/Sydney")


def compute_next_send(schedule: dict) -> datetime:
    now = datetime.now(TZ)
    send_time = schedule["send_time"]
    if isinstance(send_time, str):
        parts = send_time.split(":")
        send_time = time(int(parts[0]), int(parts[1]))
    elif hasattr(send_time, "hour"):
        send_time = time(send_time.hour, send_time.minute)

    frequency = schedule["frequency"]

    if frequency == "daily":
        candidate = datetime.combine(now.date(), send_time, TZ)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if frequency == "weekly":
        dow = schedule.get("day_of_week") or 1
        days_ahead = (dow - now.isoweekday()) % 7
        candidate = datetime.combine(now.date(), send_time, TZ) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    if frequency == "monthly":
        dom = schedule.get("day_of_month") or 1
        try:
            candidate = datetime.combine(
                date(now.year, now.month, min(dom, 28)), send_time, TZ
            )
        except ValueError:
            candidate = datetime.combine(date(now.year, now.month, 28), send_time, TZ)
        if candidate <= now:
            if now.month == 12:
                candidate = datetime.combine(date(now.year + 1, 1, min(dom, 28)), send_time, TZ)
            else:
                candidate = datetime.combine(
                    date(now.year, now.month + 1, min(dom, 28)), send_time, TZ
                )
        return candidate

    if frequency == "once":
        send_date = schedule.get("send_date")
        if isinstance(send_date, str):
            send_date = date.fromisoformat(send_date)
        return datetime.combine(send_date, send_time, TZ)

    return now + timedelta(days=1)


def generate_filter_summary(filters: dict) -> dict[str, str]:
    summary = {}
    for key in ["year", "month", "day", "measure"]:
        if key in filters and filters[key]:
            summary[key] = str(filters[key])
    for key in ["sex", "treatment", "breed", "mob", "eid"]:
        if key in filters:
            summary[key] = ", ".join(filters[key]) if isinstance(filters[key], list) else str(filters[key])
    if "measure" in filters:
        summary["measure"] = MEASURE_LABELS.get(filters["measure"], filters["measure"])
    return summary


class EmailService:
    @staticmethod
    def send_report_email(
        recipient: str,
        subject: str,
        body_html: str,
        attachment_bytes: bytes,
        attachment_name: str = "report.pdf",
    ) -> bool:
        settings = get_settings()
        if settings.email_dry_run:
            return True

        if settings.email_provider.lower() == "smtp":
            return EmailService._send_via_smtp(
                recipient, subject, body_html, attachment_bytes, attachment_name
            )
        return EmailService._send_via_resend(
            recipient, subject, body_html, attachment_bytes, attachment_name
        )

    @staticmethod
    def _send_via_smtp(
        recipient: str,
        subject: str,
        body_html: str,
        attachment_bytes: bytes,
        attachment_name: str,
    ) -> bool:
        import smtplib
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        settings = get_settings()
        if not settings.smtp_user or not settings.smtp_password:
            return False

        msg = MIMEMultipart()
        msg["From"] = settings.email_from or settings.smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
        msg.attach(part)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(msg["From"], [recipient], msg.as_string())
            return True
        except Exception:
            return False

    @staticmethod
    def _send_via_resend(
        recipient: str,
        subject: str,
        body_html: str,
        attachment_bytes: bytes,
        attachment_name: str,
    ) -> bool:
        settings = get_settings()
        if not settings.resend_api_key:
            return False
        try:
            import resend

            resend.api_key = settings.resend_api_key
            resend.Emails.send(
                {
                    "from": settings.email_from,
                    "to": recipient,
                    "subject": subject,
                    "html": body_html,
                    "attachments": [
                        {
                            "filename": attachment_name,
                            "content": base64.b64encode(attachment_bytes).decode(),
                        }
                    ],
                }
            )
            return True
        except Exception:
            return False

    @staticmethod
    def build_email_body(filters: dict, custom_body: str, farm_name: str) -> str:
        summary = generate_filter_summary(filters)
        items = "".join(f"<li>{k.title()}: {v}</li>" for k, v in summary.items())
        return f"""
        <p>Hello,</p>
        <p>Please find your automated livestock performance report for <strong>{farm_name}</strong> attached.</p>
        <p><strong>Filters applied:</strong></p>
        <ul>{items}</ul>
        <p>{custom_body}</p>
        """

    @staticmethod
    def process_due_emails() -> dict[str, int]:
        from app.db import execute, fetch_all
        from app.services.report_generator import ReportGenerator
        from app.services.data_service import DataService

        now = datetime.now(TZ)
        schedules = fetch_all(
            """
            SELECT es.*, f.farm_name
            FROM email_schedules es
            JOIN farms f ON f.farm_id = es.farm_id
            WHERE es.is_active = TRUE AND es.next_send_at <= %s
            """,
            (now,),
        )
        sent = 0
        failed = 0
        for sched in schedules:
            try:
                filters_data = sched.get("report_filters") or {}
                filters = FilterState(**{**filters_data, "farm_id": sched["farm_id"]})
                filtered, grouped, _, _ = DataService.get_filtered_data(filters, is_admin=True)
                pdf_bytes = ReportGenerator.generate_pdf(
                    filters,
                    grouped,
                    sched.get("report_charts") or [],
                    sched["farm_name"],
                    filtered_df=filtered,
                )
                subject = sched.get("email_subject") or f"Automated Livestock Report - {sched['farm_name']}"
                body = EmailService.build_email_body(
                    filters_data, sched.get("email_body") or "", sched["farm_name"]
                )
                ok = EmailService.send_report_email(
                    sched["recipient_email"], subject, body, pdf_bytes, "report.pdf"
                )
                if ok:
                    sent += 1
                    next_at = compute_next_send(sched)
                    if sched["frequency"] == "once":
                        execute(
                            "UPDATE email_schedules SET last_sent = %s, is_active = FALSE, next_send_at = NULL WHERE id = %s",
                            (now, sched["id"]),
                        )
                    else:
                        execute(
                            "UPDATE email_schedules SET last_sent = %s, next_send_at = %s WHERE id = %s",
                            (now, next_at, sched["id"]),
                        )
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {"sent": sent, "failed": failed}
