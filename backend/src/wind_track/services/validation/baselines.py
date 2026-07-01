"""Baseline scorers for validation comparisons."""

from __future__ import annotations

from typing import Any

from wind_track.services.geo import alignment_score
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG, exposure_class_for_score
from wind_track.services.scoring.scalar import clamp, score_feature


def score_flat_wind(
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Uniform exposure — no geometry multipliers."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    speed_factor = clamp(wind_speed_ms / 8.0, 0.5, cfg["reference_speed_cap_ms"] / 8.0)
    risk = clamp(speed_factor * 25, 0, 100)
    return {
        "risk_score": round(risk, 1),
        "exposure_class": exposure_class_for_score(risk, cfg),
        "local_multiplier": 1.0,
    }


def score_alignment_only(
    feature_type: str,
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Street alignment multiplier only."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    orientation = metrics.get("corridor_orientation_deg") or metrics.get("orientation_deg") or 0.0
    align = alignment_score(wind_direction_deg, orientation)
    mult = cfg["multipliers"]["alignment"]
    m_align = clamp(mult["min"] + align * (mult["max"] - mult["min"]), mult["min"], mult["max"])
    speed_factor = clamp(wind_speed_ms / 8.0, 0.5, cfg["reference_speed_cap_ms"] / 8.0)
    risk = clamp(m_align * speed_factor * 25, 0, 100)
    return {
        "risk_score": round(risk, 1),
        "exposure_class": exposure_class_for_score(risk, cfg),
        "local_multiplier": round(m_align, 3),
    }


def score_density_only(
    metrics: dict[str, Any],
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canyon H/W ratio only."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    hw = metrics.get("hw_ratio") or 1.0
    canyon = cfg["multipliers"]["canyon"]
    canyon_t = clamp((hw - canyon["hw_low"]) / (canyon["hw_high"] - canyon["hw_low"]), 0, 1)
    m_canyon = clamp(
        canyon["min"] + canyon_t * (canyon["max"] - canyon["min"]),
        canyon["min"],
        canyon["max"],
    )
    speed_factor = clamp(wind_speed_ms / 8.0, 0.5, cfg["reference_speed_cap_ms"] / 8.0)
    risk = clamp(m_canyon * speed_factor * 25, 0, 100)
    return {
        "risk_score": round(risk, 1),
        "exposure_class": exposure_class_for_score(risk, cfg),
        "local_multiplier": round(m_canyon, 3),
    }


def score_full_model(
    feature_type: str,
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full scalar v0.1 model."""
    return score_feature(feature_type, metrics, wind_direction_deg, wind_speed_ms, config)


BASELINE_SCORERS = {
    "flat_wind": lambda ft, m, d, s, c: score_flat_wind(m, d, s, c),
    "alignment_only": score_alignment_only,
    "density_only": lambda ft, m, d, s, c: score_density_only(m, s, c),
    "full_scalar": score_full_model,
}