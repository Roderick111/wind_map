"""Quay detection tests."""

import pytest

from wind_track.db.connection import fetch_all, get_db, utc_now
from wind_track.services.quay_detect import is_quay_street, promote_quay_streets
from wind_track.services.seed import seed_database


def test_is_quay_street_by_name():
    assert is_quay_street("Quai du Rhône", {})
    assert not is_quay_street("Rue de la République", {})


def test_is_quay_street_by_tag():
    assert is_quay_street("", {"man_made": "pier"})


@pytest.mark.asyncio
async def test_promote_quay_streets_no_crash_on_missing_area():
    assert await promote_quay_streets("nonexistent_area") == 0


@pytest.mark.asyncio
async def test_promote_quay_streets_on_synthetic():
    await seed_database()
    async with get_db() as conn:
        area = await fetch_all(conn, "SELECT id FROM areas WHERE slug = 'synthetic_test'")
        area_id = area[0]["id"]
        now = utc_now()
        await conn.execute(
            """INSERT INTO spatial_features
               (area_id, feature_type, name, geom, properties_json, source_object_id,
                created_at, updated_at)
               VALUES (?, 'street_segment', 'Quai Test',
                       '{"type":"LineString","coordinates":[[4.83,45.76],[4.831,45.761]]}',
                       '{}', 'test/quay1', ?, ?)""",
            (area_id, now, now),
        )
    promoted = await promote_quay_streets("synthetic_test")
    assert promoted >= 1