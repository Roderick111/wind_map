"""Validation harness tests."""

import pytest

from wind_track.services.seed import seed_database
from wind_track.services.validation.metrics import compute_validation_metrics
from wind_track.services.validation.run import run_validation_case, seed_presquile_validation_case


def test_compute_validation_metrics():
    samples = [
        {"observed_class": "high", "predicted_full": "high"},
        {"observed_class": "low", "predicted_full": "medium"},
        {"observed_class": "high", "predicted_full": "low"},
    ]
    metrics = compute_validation_metrics([
        {
            "observed_class": s["observed_class"],
            "predicted_flat": "medium",
            "predicted_alignment": s["predicted_full"],
            "predicted_density": "medium",
            "predicted_full": s["predicted_full"],
        }
        for s in samples
    ])
    assert metrics["overall_accuracy"] == pytest.approx(1 / 3, abs=0.01)
    assert metrics["high_wind_recall"] == 0.5


@pytest.mark.asyncio
async def test_validation_seed_and_run():
    await seed_database()
    seeded = await seed_presquile_validation_case("synthetic_test")
    assert seeded["samples_seeded"] == 15
    result = await run_validation_case(seeded["validation_case_id"])
    assert result["samples_scored"] > 0
    assert "overall_accuracy" in result["metrics"]
    assert "baselines" in result["metrics"]