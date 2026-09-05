"""
Vercel ASGI entrypoint.

Must expose a top-level FastAPI `app` (Vercel AST detection rejects custom handlers).

Cold-start strategy:
- health + auth + filters are registered immediately (no pandas)
- charts/summary/data/etc. load on first matching request (sql_agg has no pandas)
- pandas-heavy routers (cohorts/reports/email/admin/animals rows) load last
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, filters

settings = get_settings()

app = FastAPI(title="Livestock Dashboard API", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.app_version}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# Choices are needed on every dashboard boot — keep off the pandas import path.
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])

_loaded: set[str] = set()


def _load(group: str) -> None:
    """Import router groups lazily. charts/summary avoid pandas."""
    if group in _loaded:
        return
    if group == "charts":
        from app.routers import charts, summary

        app.include_router(charts.router, prefix="/api/charts", tags=["charts"])
        app.include_router(summary.router, prefix="/api/summary", tags=["summary"])
    elif group == "data":
        from app.routers import animals, farms

        app.include_router(farms.router, prefix="/api/farms", tags=["farms"])
        app.include_router(animals.router, prefix="/api/data", tags=["data"])
    elif group == "heavy":
        from app.routers import admin, cohorts, email_schedules, reports

        app.include_router(cohorts.router, prefix="/api/cohorts", tags=["cohorts"])
        app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
        app.include_router(email_schedules.router, prefix="/api/email", tags=["email"])
        app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    _loaded.add(group)


@app.middleware("http")
async def ensure_routers(request: Request, call_next):
    path = request.url.path
    if path.rstrip("/") == "/api/health" or path.startswith("/api/auth") or path.startswith("/api/filters"):
        return await call_next(request)
    if path.startswith("/api/charts") or path.startswith("/api/summary"):
        _load("charts")
    elif path.startswith("/api/data") or path.startswith("/api/farms"):
        _load("data")
    elif path.startswith("/api/"):
        # Remaining API surface may need several groups (e.g. reports → data helpers).
        _load("charts")
        _load("data")
        _load("heavy")
    return await call_next(request)
