"""Scalar wind exposure scoring engine."""

from __future__ import annotations

from typing import Any

from wind_track.services.geo import alignment_score
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG, exposure_class_for_score
from wind_track.services.scoring.gust import gust_risk_boost, weather_gust_elevated
from wind_track.services.scoring.special_rules import apply_special_rules


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value to range."""
    return max(low, min(high, value))


def compute_subscores(
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Compute decomposed sub-scores."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    mult = cfg["multipliers"]
    orientation = metrics.get("corridor_orientation_deg") or metrics.get("orientation_deg") or 0.0
    hw = metrics.get("hw_ratio") or 1.0
    enclosure = metrics.get("enclosure_ratio") or 0.5
    vegetation = metrics.get("vegetation_density") or 0.0
    slope = metrics.get("slope_deg") or 0.0

    align = alignment_score(wind_direction_deg, orientation)
    m_align = clamp(
        mult["alignment"]["min"] + align * (mult["alignment"]["max"] - mult["alignment"]["min"]),
        mult["alignment"]["min"],
        mult["alignment"]["max"],
    )

    canyon_t = clamp((hw - mult["canyon"]["hw_low"]) / (mult["canyon"]["hw_high"] - mult["canyon"]["hw_low"]), 0, 1)
    m_canyon = clamp(
        mult["canyon"]["min"] + canyon_t * (mult["canyon"]["max"] - mult["canyon"]["min"]),
        mult["canyon"]["min"],
        mult["canyon"]["max"],
    )

    highrise = metrics.get("nearby_highrise_score") or 0.0
    m_downwash = clamp(1.0 + highrise * 0.5, mult["downwash"]["min"], mult["downwash"]["max"])
    corner_align = alignment_score(wind_direction_deg, (orientation + 90) % 360)
    m_corner = clamp(1.0 + corner_align * 0.4, mult["corner"]["min"], mult["corner"]["max"])
    m_gap = clamp(1.0 + (1 - enclosure) * 0.3, mult["gap"]["min"], mult["gap"]["max"])
    m_open = clamp(1.0 + (1 - enclosure) * 0.5, mult["open"]["min"], mult["open"]["max"])
    m_shield = clamp(0.5 + enclosure * 0.5, mult["shielding"]["min"], mult["shielding"]["max"])
    m_veg = clamp(1.0 - vegetation * 0.3, mult["vegetation"]["min"], mult["vegetation"]["max"])

    aspect = metrics.get("slope_aspect_deg") or 0.0
    windward = abs((wind_direction_deg - aspect + 180) % 360 - 180) < 45
    m_terrain = clamp(1.3 if windward and slope > 3 else 0.9, mult["terrain"]["min"], mult["terrain"]["max"])

    data_conf = metrics.get("metric_confidence") or 0.7
    model_conf = 0.8 if metrics.get("handling_mode") == "normal_score" else 0.55

    return {
        "directional_alignment": round(align, 3),
        "m_alignment": round(m_align, 3),
        "m_canyon": round(m_canyon, 3),
        "m_downwash": round(m_downwash, 3),
        "m_corner": round(m_corner, 3),
        "m_gap": round(m_gap, 3),
        "m_open": round(m_open, 3),
        "m_shielding": round(m_shield, 3),
        "m_vegetation": round(m_veg, 3),
        "m_terrain": round(m_terrain, 3),
        "data_confidence": round(data_conf, 3),
        "model_suitability_confidence": round(model_conf, 3),
        "reference_wind_speed_ms": wind_speed_ms,
    }


def score_feature(
    feature_type: str,
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
    config: dict[str, Any] | None = None,
    wind_gust_ms: float | None = None,
) -> dict[str, Any]:
    """Score a single feature for a wind scenario."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    special = apply_special_rules(feature_type, metrics, wind_direction_deg, wind_speed_ms)
    handling_mode = special["handling_mode"]

    if handling_mode == "excluded":
        return {
            "risk_score": 0.0,
            "exposure_class": "low",
            "local_multiplier": 1.0,
            "approx_local_speed_ms": 0.0,
            "gust_sensitive": False,
            "confidence": max(0.1, 0.5 - special["confidence_penalty"]),
            "handling_mode": handling_mode,
            "subscores": {},
            "cause_tags": special["cause_tags"],
            "mitigation_tags": special["mitigation_tags"],
            "model_note": special["model_note"],
            "limitations": special["limitations"],
        }

    subscores = compute_subscores(metrics, wind_direction_deg, wind_speed_ms, cfg)
    m_special = special["m_special"]
    local_multiplier = (
        subscores["m_alignment"]
        * subscores["m_canyon"]
        * subscores["m_downwash"]
        * subscores["m_corner"]
        * subscores["m_gap"]
        * subscores["m_open"]
        * subscores["m_shielding"]
        * subscores["m_vegetation"]
        * subscores["m_terrain"]
        * m_special
    )
    subscores["m_special_geometry"] = round(m_special, 3)
    subscores["local_multiplier"] = round(local_multiplier, 3)

    ref_cap = cfg["reference_speed_cap_ms"]
    speed_factor = clamp(wind_speed_ms / 8.0, 0.5, ref_cap / 8.0)
    geom_gust = 1.1 if special["gust_sensitive"] else 1.0
    wx_gust = gust_risk_boost(wind_speed_ms, wind_gust_ms, cfg)
    gust_boost = max(geom_gust, wx_gust)
    raw_score = local_multiplier * speed_factor * gust_boost * 25
    risk_score = clamp(raw_score, 0, 100)

    data_conf = subscores["data_confidence"]
    model_conf = subscores["model_suitability_confidence"]
    confidence = clamp((data_conf + model_conf) / 2 - special["confidence_penalty"], 0.1, 0.95)

    cause_tags = list(special["cause_tags"])
    if subscores["directional_alignment"] > 0.7:
        cause_tags.append("wind_aligned_corridor")
    if (metrics.get("hw_ratio") or 0) > 1.5:
        cause_tags.append("deep_street_canyon")
    if (metrics.get("vegetation_density") or 0) > 0.4:
        cause_tags.append("vegetation_shelter")

    approx_speed = wind_speed_ms * local_multiplier

    return {
        "risk_score": round(risk_score, 1),
        "exposure_class": exposure_class_for_score(risk_score, cfg),
        "local_multiplier": round(local_multiplier, 3),
        "approx_local_speed_ms": round(approx_speed, 2),
        "gust_sensitive": special["gust_sensitive"] or weather_gust_elevated(
            wind_speed_ms, wind_gust_ms, cfg,
        ),
        "confidence": round(confidence, 3),
        "handling_mode": handling_mode,
        "subscores": subscores,
        "cause_tags": cause_tags,
        "mitigation_tags": special["mitigation_tags"],
        "model_note": special["model_note"],
        "limitations": special["limitations"],
    }