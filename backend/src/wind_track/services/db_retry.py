"""SQLite busy-lock retries for concurrent API requests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiosqlite

T = TypeVar("T")

MAX_DB_RETRIES = 6


async def with_db_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    label: str = "db",
) -> T:
    """Retry coroutine on SQLite 'database is locked' with exponential backoff."""
    delay = 0.05
    last_exc: Exception | None = None
    for attempt in range(MAX_DB_RETRIES):
        try:
            return await fn()
        except aiosqlite.OperationalError as exc:
            last_exc = exc
            if "locked" not in str(exc).lower() or attempt == MAX_DB_RETRIES - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 1.0)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{label} retry failed")