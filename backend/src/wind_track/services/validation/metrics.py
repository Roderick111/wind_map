"""Validation metric calculations."""

from __future__ import annotations

from typing import Any

HIGH_CLASSES = {"high", "very_high"}
ADJACENT: dict[str, set[str]] = {
    "low": {"low", "medium"},
    "medium": {"low", "medium", "high"},
    "high": {"medium", "high", "very_high"},
    "very_high": {"high", "very_high"},
}


def compute_validation_metrics(
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute accuracy, high-wind recall, and per-baseline comparison."""
    if not samples:
        return {"overall_accuracy": 0.0, "sample_count": 0, "baselines": {}}

    def _metrics_for_key(pred_key: str) -> dict[str, Any]:
        correct = 0
        high_obs = 0
        high_hit = 0
        high_pred = 0
        adjacent = 0
        false_neg = 0
        for row in samples:
            obs = row.get("observed_class")
            pred = row.get(pred_key)
            if not obs or not pred:
                continue
            if obs == pred:
                correct += 1
            if pred in ADJACENT.get(obs, {obs}):
                adjacent += 1
            if obs in HIGH_CLASSES:
                high_obs += 1
                if pred in HIGH_CLASSES:
                    high_hit += 1
                else:
                    false_neg += 1
            if pred in HIGH_CLASSES:
                high_pred += 1
        n = len(samples)
        return {
            "overall_accuracy": round(correct / n, 3) if n else 0.0,
            "high_wind_recall": round(high_hit / high_obs, 3) if high_obs else None,
            "high_wind_precision": round(high_hit / high_pred, 3) if high_pred else None,
            "adjacent_class_accuracy": round(adjacent / n, 3) if n else 0.0,
            "false_negative_rate": round(false_neg / high_obs, 3) if high_obs else None,
            "sample_count": n,
        }

    baselines: dict[str, Any] = {}
    for key in ("predicted_flat", "predicted_alignment", "predicted_density", "predicted_full"):
        baselines[key] = _metrics_for_key(key)

    return {
        **_metrics_for_key("predicted_full"),
        "baselines": baselines,
        "confusion": _confusion_matrix(samples, "observed_class", "predicted_full"),
    }


def _confusion_matrix(
    samples: list[dict[str, Any]],
    obs_key: str,
    pred_key: str,
) -> dict[str, dict[str, int]]:
    classes = ["low", "medium", "high", "very_high"]
    matrix = {o: {p: 0 for p in classes} for o in classes}
    for row in samples:
        obs = row.get(obs_key)
        pred = row.get(pred_key)
        if obs in matrix and pred in matrix[obs]:
            matrix[obs][pred] += 1
    return matrix