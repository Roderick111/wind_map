"""Directional cache unit and API tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from wind_track.main import app
from wind_track.services.directional_cache import (
    PRECOMPUTE_REF_SPEED_MS,
    scale_risk_score,
    snap_direction,
)
from wind_track.services.precompute import precompute_directions
from wind_track.services.seed import seed_database


def test_snap_direction_nearest_bearing():
    assert snap_direction(10) == 0
    assert snap_direction(44) == 45
    assert snap_direction(350) == 0
    assert snap_direction(170) == 180


def test_scale_risk_score_same_speed():
    cached = 42.0
    scaled = scale_risk_score(cached, PRECOMPUTE_REF_SPEED_MS)
    assert scaled == pytest.approx(cached)


def test_scale_risk_score_higher_speed():
    cached = 40.0
    scaled = scale_risk_score(cached, 16.0)
    assert scaled > cached


@pytest.fixture
async def client_with_cache():
    await seed_database()
    await precompute_directions("synthetic_test")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_cached_exposure_endpoint(client_with_cache: AsyncClient):
    resp = await client_with_cache.get(
        "/areas/synthetic_test/exposure",
        params={"direction_deg": 88, "wind_speed_ms": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert data[0]["cache_hit"] is True
    assert data[0]["cache_direction_deg"] == 90


@pytest.mark.asyncio
async def test_cached_exposure_accepts_360_direction(client_with_cache: AsyncClient):
    resp = await client_with_cache.get(
        "/areas/synthetic_test/exposure",
        params={"direction_deg": 360, "wind_speed_ms": 8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["cache_direction_deg"] == 0


@pytest.mark.asyncio
async def test_cache_status_endpoint(client_with_cache: AsyncClient):
    resp = await client_with_cache.get("/areas/synthetic_test/cache-status")
    assert resp.status_code == 200
    status = resp.json()
    assert status["ready"] is True
    assert status["entry_count"] > 0