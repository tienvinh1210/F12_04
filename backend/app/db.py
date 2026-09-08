from __future__ import annotations

import contextlib
import os
from typing import Any, Generator

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from app.config import get_settings

_pool: SimpleConnectionPool | None = None
_serverless_conn = None
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _connect():
    settings = get_settings()
    # Keepalives help detect dead Supabase pooler sockets after a warm freeze.
    return psycopg2.connect(
        settings.database_url,
        connect_timeout=3,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = SimpleConnectionPool(1, 5, settings.database_url, connect_timeout=5)
    return _pool


def _reset_serverless_conn() -> None:
    global _serverless_conn
    if _serverless_conn is not None:
        with contextlib.suppress(Exception):
            _serverless_conn.close()
        _serverless_conn = None


@contextlib.contextmanager
def get_conn() -> Generator[Any, None, None]:
    # Reuse one connection per warm serverless instance — opening SSL to Supabase
    # on every fetch_all call was the main latency source after cold start.
    if IS_SERVERLESS:
        global _serverless_conn
        if _serverless_conn is None or _serverless_conn.closed:
            _serverless_conn = _connect()
        conn = _serverless_conn
        try:
            yield conn
            conn.commit()
        except Exception:
            with contextlib.suppress(Exception):
                conn.rollback()
            _reset_serverless_conn()
            raise
        return

    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def fetch_all(query: str, params: tuple | dict | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def fetch_one(query: str, params: tuple | dict | None = None) -> dict | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: tuple | dict | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount


def execute_returning(query: str, params: tuple | dict | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None


def user_has_farm(user_id: int, farm_id: str) -> bool:
    row = fetch_one(
        "SELECT 1 FROM user_farm_access WHERE user_id = %s AND farm_id = %s",
        (user_id, farm_id),
    )
    return row is not None


def get_user_farms(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT f.farm_id, f.farm_name, f.slug
        FROM farms f
        JOIN user_farm_access ufa ON ufa.farm_id = f.farm_id
        WHERE ufa.user_id = %s AND f.is_active = TRUE
        ORDER BY f.farm_name
        """,
        (user_id,),
    )
