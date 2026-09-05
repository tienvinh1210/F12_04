"""
Slim Vercel entrypoint for login / health / filter choices.

Kept free of pandas/matplotlib/reportlab so cold starts stay small.
Heavy chart/data routes stay on api/index.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, filters

settings = get_settings()

app = FastAPI(title="Livestock Dashboard API (light)", version=settings.app_version)
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
    return {"status": "ok", "version": settings.app_version, "tier": "light"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
