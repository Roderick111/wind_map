"""Open-Meteo weather ingestion."""

from __future__ import annotations

from typing import Any

import httpx

from wind_track.config.settings import settings
from wind_track.db.connection import dumps_json, get_db, utc_now


async def fetch_open_meteo(lat: float, lon: float) -> dict[str, Any]:
    """Fetch current and hourly forecast wind from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "forecast_days": 2,
        "timezone": "Europe/Paris",
        "wind_speed_unit": "ms",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(settings.open_meteo_url, params=params)
        resp.raise_for_status()
        return resp.json()


async def cache_weather_for_area(area_id: int, lat: float, lon: float) -> list[int]:
    """Store current + forecast observations; return inserted IDs."""
    try:
        payload = await fetch_open_meteo(lat, lon)
    except httpx.HTTPError:
        return await _latest_cached_ids(area_id)

    now = utc_now()
    ids: list[int] = []
    current = payload.get("current", {})
    async with get_db() as conn:
        await conn.execute(
            "DELETE FROM weather_observations WHERE area_id = ? AND is_forecast = 1",
            (area_id,),
        )
        cursor = await conn.execute(
            """INSERT INTO weather_observations
               (area_id, source, model, latitude, longitude, timestamp, is_forecast,
                wind_speed_10m_ms, wind_direction_10m_deg, wind_gust_10m_ms, raw_payload_json, created_at)
               VALUES (?, 'open_meteo', ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
            (
                area_id,
                payload.get("model", "best_match"),
                lat, lon,
                current.get("time", now),
                current.get("wind_speed_10m"),
                current.get("wind_direction_10m"),
                current.get("wind_gusts_10m"),
                dumps_json({"current": current, "units": payload.get("current_units", {})}),
                now,
            ),
        )
        ids.append(cursor.lastrowid or 0)

        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        for i, ts in enumerate(times[:48]):
            cursor = await conn.execute(
                """INSERT INTO weather_observations
                   (area_id, source, model, latitude, longitude, timestamp, forecast_timestamp,
                    is_forecast, wind_speed_10m_ms, wind_direction_10m_deg, wind_gust_10m_ms,
                    raw_payload_json, created_at)
                   VALUES (?, 'open_meteo', ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)""",
                (
                    area_id,
                    payload.get("model", "best_match"),
                    lat,
                    lon,
                    now,
                    ts,
                    _safe_idx(hourly.get("wind_speed_10m"), i),
                    _safe_idx(hourly.get("wind_direction_10m"), i),
                    _safe_idx(hourly.get("wind_gusts_10m"), i),
                    dumps_json({"hour_index": i}),
                    now,
                ),
            )
            ids.append(cursor.lastrowid or 0)
    return ids


async def _latest_cached_ids(area_id: int) -> list[int]:
    """Return latest cached observation IDs on fetch failure."""
    async with get_db() as conn:
        rows = await conn.execute_fetchall(
            """SELECT id FROM weather_observations
               WHERE area_id = ? ORDER BY created_at DESC LIMIT 1""",
            (area_id,),
        )
        return [r[0] for r in rows]


async def get_current_weather(area_id: int) -> dict[str, Any] | None:
    """Get latest non-forecast observation for area."""
    async with get_db() as conn:
        row = await conn.execute_fetchall(
            """SELECT * FROM weather_observations
               WHERE area_id = ? AND is_forecast = 0
               ORDER BY created_at DESC LIMIT 1""",
            (area_id,),
        )
        if not row:
            return None
        cols = [d[1] for d in await conn.execute_fetchall("PRAGMA table_info(weather_observations)")]
        return dict(zip(cols, row[0], strict=False))


async def get_forecast(area_id: int) -> list[dict[str, Any]]:
    """Get latest hourly forecast batch for area."""
    async with get_db() as conn:
        rows = await conn.execute_fetchall(
            """SELECT * FROM weather_observations
               WHERE area_id = ? AND is_forecast = 1
                 AND created_at = (
                   SELECT MAX(created_at) FROM weather_observations
                   WHERE area_id = ? AND is_forecast = 1
                 )
               ORDER BY forecast_timestamp LIMIT 48""",
            (area_id, area_id),
        )
        cols = [d[1] for d in await conn.execute_fetchall("PRAGMA table_info(weather_observations)")]
        return [dict(zip(cols, r, strict=False)) for r in rows]


def _safe_idx(values: list[Any] | None, idx: int) -> Any:
    if not values or idx >= len(values):
        return None
    return values[idx]