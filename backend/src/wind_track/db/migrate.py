"""Database migration runner."""

from __future__ import annotations

from pathlib import Path

from wind_track.config.settings import settings
from wind_track.db.connection import get_db, utc_now

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
MIGRATION_VERSION = "2026-07-01-v05"


async def run_migrations(db_path: Path | None = None) -> None:
    """Apply schema migrations idempotently."""
    schema_sql = SCHEMA_PATH.read_text()
    async with get_db(db_path) as conn:
        await conn.executescript(schema_sql)
        existing = await conn.execute_fetchall(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (MIGRATION_VERSION,),
        )
        if not existing:
            await conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (MIGRATION_VERSION, utc_now()),
            )


async def ensure_database() -> None:
    """Ensure database exists and schema is applied."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    await run_migrations()