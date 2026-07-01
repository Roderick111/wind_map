"""Priority zone seeding tests."""

import pytest

from wind_track.services.priority_zones import seed_priority_zones
from wind_track.services.seed import seed_database


@pytest.mark.asyncio
async def test_seed_priority_zones_synthetic_noop():
    await seed_database()
    result = await seed_priority_zones("synthetic_test")
    assert result["features_added"] == 0