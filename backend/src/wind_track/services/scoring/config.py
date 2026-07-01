"""Scalar model configuration."""

from __future__ import annotations

DEFAULT_SCALAR_CONFIG: dict = {
    "exposure_thresholds": {
        "low": [0, 25],
        "medium": [26, 50],
        "high": [51, 75],
        "very_high": [76, 100],
    },
    "multipliers": {
        "alignment": {"min": 0.6, "max": 1.8},
        "canyon": {"hw_low": 0.5, "hw_high": 2.0, "min": 0.7, "max": 1.6},
        "downwash": {"min": 1.0, "max": 1.5},
        "corner": {"min": 1.0, "max": 1.4},
        "gap": {"min": 1.0, "max": 1.5},
        "open": {"min": 0.8, "max": 1.7},
        "shielding": {"min": 0.5, "max": 1.0},
        "vegetation": {"min": 0.7, "max": 1.0},
        "terrain": {"min": 0.8, "max": 1.4},
        "special_geometry": {"min": 0.8, "max": 2.0},
    },
    "reference_speed_cap_ms": 25.0,
    "gust_factor": 1.3,
    "gust_ratio_threshold": 1.35,
}


def exposure_class_for_score(score: float, config: dict) -> str:
    """Map risk score to exposure class using config thresholds."""
    thresholds = config["exposure_thresholds"]
    for cls, bounds in thresholds.items():
        if bounds[0] <= score <= bounds[1]:
            return cls
    return "very_high"