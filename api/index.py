"""
Vercel ASGI entrypoint.

Must expose a top-level FastAPI `app` (Vercel AST detection rejects custom handlers).
Health + auth are registered immediately (no pandas). Remaining routers load on
first non-auth request so login cold starts stay fast.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth

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

_heavy_loaded = False


def _load_heavy_routers() -> None:
    """Import pandas-backed routers only when a dashboard API route is hit."""
    global _heavy_loaded
    if _heavy_loaded:
        return
    from app.routers import (
        admin,
        animals,
        charts,
        cohorts,
        email_schedules,
        farms,
        filters,
        reports,
        summary,
    )

    app.include_router(farms.router, prefix="/api/farms", tags=["farms"])
    app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
    app.include_router(animals.router, prefix="/api/data", tags=["data"])
    app.include_router(summary.router, prefix="/api/summary", tags=["summary"])
    app.include_router(charts.router, prefix="/api/charts", tags=["charts"])
    app.include_router(cohorts.router, prefix="/api/cohorts", tags=["cohorts"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(email_schedules.router, prefix="/api/email", tags=["email"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    _heavy_loaded = True


@app.middleware("http")
async def ensure_heavy_routers(request: Request, call_next):
    path = request.url.path
    if path.rstrip("/") != "/api/health" and not path.startswith("/api/auth"):
        _load_heavy_routers()
    return await call_next(request)
