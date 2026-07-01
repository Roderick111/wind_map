"""Quality audit tests."""

import pytest

from wind_track.services.quality_audit import run_quality_audit
from wind_track.services.seed import seed_database


@pytest.mark.asyncio
async def test_quality_audit_synthetic():
    await seed_database()
    report = await run_quality_audit("synthetic_test")
    assert report["area_slug"] == "synthetic_test"
    assert "buildings" in report
    assert "priority_checks" in report