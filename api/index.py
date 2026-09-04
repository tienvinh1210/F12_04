"""
Vercel entrypoint.

Health + auth use a slim FastAPI app (no pandas/numpy) so login cold starts
stay under ~1.5s. All other /api routes load the full dashboard app lazily.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _event_path(event: dict) -> str:
    path = (
        event.get("rawPath")
        or event.get("path")
        or (event.get("requestContext") or {}).get("http", {}).get("path")
        or ""
    )
    return str(path)


def _is_health(path: str) -> bool:
    p = path.rstrip("/")
    return p.endswith("/api/health") or p.endswith("/health")


def _is_auth(path: str) -> bool:
    return "/api/auth" in path


class _LazyMangum:
    def __init__(self):
        self._health_auth = None
        self._full = None

    def __call__(self, event, context):
        path = _event_path(event)

        # Ultra-fast health — no framework import on the hottest warmup path.
        if _is_health(path):
            return {
                "statusCode": 200,
                "headers": {
                    "content-type": "application/json",
                    "cache-control": "no-store",
                },
                "body": json.dumps({"status": "ok", "version": "1.0.0"}),
            }

        from mangum import Mangum

        if _is_auth(path):
            if self._health_auth is None:
                from app.auth_app import app as auth_app

                self._health_auth = Mangum(auth_app, lifespan="off")
            return self._health_auth(event, context)

        if self._full is None:
            from app.main import app as full_app

            self._full = Mangum(full_app, lifespan="off")
        return self._full(event, context)


handler = _LazyMangum()
