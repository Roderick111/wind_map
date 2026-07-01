"""Height enrichment tests."""

from unittest.mock import AsyncMock, patch

import pytest

from wind_track.services.enrich_heights import enrich_building_heights
from wind_track.services.seed import seed_database


@pytest.mark.asyncio
async def test_enrich_heights_no_lock_on_metrics_recompute():
    """Metrics recompute must not nest a second DB connection inside enrich."""
    await seed_database()
    result = await enrich_building_heights("synthetic_test")
    assert "neighborhood_updated" in result
    assert "bdtopo_updated" in result
    assert result["metrics_recomputed"] >= 0


@pytest.mark.asyncio
async def test_enrich_heights_applies_bdtopo_match():
    from wind_track.db.connection import fetch_all, get_db, loads_json

    await seed_database()
    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT f.id FROM spatial_features f
               JOIN areas a ON a.id = f.area_id
               WHERE a.slug = 'synthetic_test' AND f.feature_type = 'building'
               LIMIT 1""",
        )
    building_id = rows[0]["id"]
    with patch(
        "wind_track.services.enrich_heights._fetch_bdtopo_matches",
        new=AsyncMock(return_value=({building_id: 22.0}, 1)),
    ):
        result = await enrich_building_heights("synthetic_test", recompute_metrics=False)
    assert result["bdtopo_updated"] == 1
    async with get_db() as conn:
        row = await fetch_all(
            conn,
            "SELECT properties_json FROM spatial_features WHERE id = ?",
            (building_id,),
        )
    props = loads_json(row[0]["properties_json"], {})
    assert props["height_source"] == "bdtopo"
    assert props["height_m"] == 22.0