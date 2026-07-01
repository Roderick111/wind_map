"""OSM import persistence and skip logic."""

import pytest

from wind_track.config.settings import settings
from wind_track.services.import_osm import area_import_status, import_osm_area
from wind_track.services.seed import seed_database


def test_tests_use_isolated_database():
    assert settings.db_path.name == ".test_wind_track.db"


@pytest.mark.asyncio
async def test_import_skips_when_osm_already_present(monkeypatch):
    called = {"fetch": False}

    async def fake_fetch(_bbox: str):
        called["fetch"] = True
        return []

    async def fake_status(_slug: str):
        return {
            "imported": True,
            "street_count": 120,
            "feature_count": 500,
            "data_version": "pilot_presquile-osm-2026-07-01",
            "source_type": "osm",
        }

    monkeypatch.setattr("wind_track.services.import_osm.fetch_overpass", fake_fetch)
    monkeypatch.setattr("wind_track.services.import_osm.area_import_status", fake_status)
    async def fake_cache(_slug: str):
        return {"ready": True, "entry_count": 100}

    monkeypatch.setattr("wind_track.services.import_osm.cache_status", fake_cache)

    result = await import_osm_area("pilot_presquile", force=False)
    assert result.get("skipped") is True
    assert called["fetch"] is False


@pytest.mark.asyncio
async def test_area_import_status_empty():
    await seed_database()
    status = await area_import_status("synthetic_test")
    assert status["imported"] is False