"""Weather ingestion tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from wind_track.main import app
from wind_track.services.seed import seed_database
from wind_track.services.weather.open_meteo import (
    cache_weather_for_area,
    fetch_open_meteo,
    get_forecast,
)


@pytest.mark.asyncio
async def test_cache_weather_sql_bindings(monkeypatch):
    seeded = await seed_database()
    area_id = seeded["area_id"]
    async def fake_fetch(_lat: float, _lon: float):
        return {
            "current": {
                "time": "2026-07-01T12:00",
                "wind_speed_10m": 5.0,
                "wind_direction_10m": 180,
                "wind_gusts_10m": 8.0,
            },
            "hourly": {
                "time": ["2026-07-01T13:00", "2026-07-01T14:00"],
                "wind_speed_10m": [6.0, 7.0],
                "wind_direction_10m": [190, 200],
                "wind_gusts_10m": [9.0, 10.0],
            },
        }

    monkeypatch.setattr(
        "wind_track.services.weather.open_meteo.fetch_open_meteo",
        fake_fetch,
    )
    ids = await cache_weather_for_area(area_id, 45.764, 4.8357)
    assert len(ids) == 3


@pytest.mark.asyncio
async def test_get_forecast_returns_latest_batch_only(monkeypatch):
    seeded = await seed_database()
    area_id = seeded["area_id"]

    async def fake_fetch(_lat: float, _lon: float):
        return {
            "current": {"time": "2026-07-01T12:00", "wind_speed_10m": 5.0},
            "hourly": {
                "time": ["2026-07-01T13:00"],
                "wind_speed_10m": [6.0],
                "wind_direction_10m": [190],
                "wind_gusts_10m": [9.0],
            },
        }

    monkeypatch.setattr(
        "wind_track.services.weather.open_meteo.fetch_open_meteo",
        fake_fetch,
    )
    await cache_weather_for_area(area_id, 45.764, 4.8357)
    await cache_weather_for_area(area_id, 45.764, 4.8357)
    rows = await get_forecast(area_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_weather_forecast_endpoint(monkeypatch):
    seeded = await seed_database()
    area_id = seeded["area_id"]

    async def fake_fetch(_lat: float, _lon: float):
        return {
            "current": {"time": "2026-07-01T12:00", "wind_speed_10m": 5.0},
            "hourly": {
                "time": ["2026-07-01T13:00", "2026-07-01T14:00"],
                "wind_speed_10m": [6.0, 7.0],
                "wind_direction_10m": [190, 200],
                "wind_gusts_10m": [9.0, 10.0],
            },
        }

    monkeypatch.setattr(
        "wind_track.services.weather.open_meteo.fetch_open_meteo",
        fake_fetch,
    )
    await cache_weather_for_area(area_id, 45.764, 4.8357)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/weather/forecast?area_id={area_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["is_forecast"] is True
    assert data[0]["wind_speed_10m_ms"] == 6.0


@pytest.mark.asyncio
async def test_fetch_open_meteo_uses_ms_units():
    payload = await fetch_open_meteo(45.761, 4.835)
    units = payload.get("current_units", {})
    assert units.get("wind_speed_10m") == "m/s"
    speed = payload.get("current", {}).get("wind_speed_10m")
    assert speed is not None
    assert speed < 15, "Wind speed should be plausible m/s, not km/h"