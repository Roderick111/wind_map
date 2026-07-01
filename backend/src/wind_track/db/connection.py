"""SQLite connection helpers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from wind_track.config.settings import settings


def utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


def dumps_json(value: Any) -> str:
    """Serialize value to JSON string."""
    return json.dumps(value, separators=(",", ":"))


def loads_json(value: str | None, default: Any) -> Any:
    """Deserialize JSON string with fallback."""
    if not value:
        return default
    return json.loads(value)


@asynccontextmanager
async def get_db(db_path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection with row factory."""
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(path, timeout=30.0)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def fetch_one(
    conn: aiosqlite.Connection,
    query: str,
    params: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    """Fetch single row as dict."""
    cursor = await conn.execute(query, params)
    row = await cursor.fetchone()
    return dict(row) if row else None


async def fetch_all(
    conn: aiosqlite.Connection,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    """Fetch all rows as dicts."""
    cursor = await conn.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]