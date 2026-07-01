"""API integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from wind_track.main import app
from wind_track.services.precompute import precompute_directions
from wind_track.services.seed import seed_database


@pytest.fixture
async def client_with_cache():
    await seed_database()
    await precompute_directions("synthetic_test")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client():
    await seed_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_areas(client: AsyncClient):
    resp = await client.get("/areas")
    assert resp.status_code == 200
    areas = resp.json()
    slugs = {a["slug"] for a in areas}
    assert "synthetic_test" in slugs


@pytest.mark.asyncio
async def test_scalar_scenario_flow(client: AsyncClient):
    resp = await client.post(
        "/scenarios/scalar",
        json={
            "area_slug": "synthetic_test",
            "wind_speed_ms": 10,
            "wind_direction_deg": 90,
            "scenario_type": "manual",
        },
    )
    assert resp.status_code == 200
    scenario = resp.json()
    scenario_id = scenario["scenario_id"]
    assert scenario["feature_count"] > 0

    results = await client.get(f"/scenarios/{scenario_id}/results")
    assert results.status_code == 200
    data = results.json()
    assert len(data) > 0
    bridge = next((r for r in data if r["feature_type"] == "bridge"), None)
    assert bridge is not None
    assert bridge["handling_mode"] == "special_rule"


@pytest.mark.asyncio
async def test_data_quality_height_tiers(client: AsyncClient):
    areas = (await client.get("/areas")).json()
    area = next(a for a in areas if a["slug"] == "synthetic_test")
    resp = await client.get(f"/areas/{area['id']}/data-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "estimated_height_coverage" in data
    total = (
        data["official_height_coverage"]
        + data["estimated_height_coverage"]
        + data["fallback_height_coverage"]
    )
    assert total <= 1.01


@pytest.mark.asyncio
async def test_tile_manifest_endpoint(client: AsyncClient):
    areas = (await client.get("/areas")).json()
    area = next(a for a in areas if a["slug"] == "synthetic_test")
    resp = await client.get(f"/areas/{area['slug']}/tiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["area_slug"] == "synthetic_test"
    assert "ready" in data


@pytest.mark.asyncio
async def test_scalar_rejected_when_cache_ready_and_area_large(
    client_with_cache: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from wind_track.api import routes

    monkeypatch.setattr(routes, "LARGE_AREA_FEATURE_LIMIT", 1)
    resp = await client_with_cache.post(
        "/scenarios/scalar",
        json={
            "area_slug": "synthetic_test",
            "wind_speed_ms": 10,
            "wind_direction_deg": 90,
            "scenario_type": "manual",
        },
    )
    assert resp.status_code == 409
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_flow_indicators_endpoint(client_with_cache: AsyncClient):
    resp = await client_with_cache.get(
        "/areas/synthetic_test/flow",
        params={"direction_deg": 90, "wind_speed_ms": 8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_area_summary_cache_fields(client: AsyncClient):
    areas = (await client.get("/areas")).json()
    area = next(a for a in areas if a["slug"] == "synthetic_test")
    resp = await client.get(f"/areas/{area['id']}/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert "cache_ready" in summary
    assert "cache_entries" in summary