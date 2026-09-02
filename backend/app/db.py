from __future__ import annotations

import contextlib
from typing import Any, Generator

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from app.config import get_settings

_pool: SimpleConnectionPool | None = None


def get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = SimpleConnectionPool(1, 10, settings.database_url)
    return _pool


@contextlib.contextmanager
def get_conn() -> Generator[Any, None, None]:
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
