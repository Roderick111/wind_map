"""Special geometry scoring rules."""

from __future__ import annotations

from typing import Any

from wind_track.services.geo import alignment_score, angle_diff_deg


def apply_special_rules(
    feature_type: str,
    metrics: dict[str, Any],
    wind_direction_deg: float,
    wind_speed_ms: float,
) -> dict[str, Any]:
    """Apply feature-type-specific scoring adjustments."""
    handlers = {
        "bridge": _score_bridge,
        "quay": _score_quay,
        "open_space": _score_open_space,
        "irregular_fabric_zone": _score_irregular_fabric,
        "slope_zone": _score_slope,
        "tunnel": _score_tunnel,
        "underpass": _score_tunnel,
        "high_rise_cluster": _score_high_rise,
    }
    handler = handlers.get(feature_type)
    if handler:
        return handler(metrics, wind_direction_deg, wind_speed_ms)
    return {
        "handling_mode": metrics.get("handling_mode", "normal_score"),
        "m_special": 1.0,
        "cause_tags": [],
        "mitigation_tags": [],
        "model_note": None,
        "limitations": [],
        "confidence_penalty": 0.0,
        "gust_sensitive": False,
    }


def _score_bridge(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    river_axis = metrics.get("river_axis_deg") or 0.0
    orientation = metrics.get("orientation_deg") or 0.0
    aligned_river = alignment_score(wind_deg, river_axis) > 0.7
    crosswind = angle_diff_deg(wind_deg, orientation) > 60
    m = 1.4
    tags = ["bridge_exposure", "open_water_fetch"]
    if aligned_river:
        m *= 1.2
        tags.append("river_aligned_wind")
    if crosswind:
        tags.append("crosswind_discomfort")
    return {
        "handling_mode": "special_rule",
        "m_special": min(m, 2.0),
        "cause_tags": tags,
        "mitigation_tags": [],
        "model_note": "Bridge crossing uses exposed open-water fetch rules.",
        "limitations": ["Complex bridge structure lowers confidence."],
        "confidence_penalty": 0.15 if metrics.get("nearby_highrise_score", 0) > 0.5 else 0.05,
        "gust_sensitive": crosswind,
    }


def _score_quay(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    river_axis = metrics.get("river_axis_deg") or 90.0
    river_dist = metrics.get("river_distance_m") or 10.0
    aligned = alignment_score(wind_deg, river_axis)
    m = 1.2 + (0.4 * aligned) + max(0, (30 - river_dist) / 100)
    tags = ["river_corridor", "quay_exposure"]
    if aligned > 0.7:
        tags.append("open_fetch")
    if metrics.get("special_geometry_type") == "open_exit_transition":
        tags.append("gust_transition")
    return {
        "handling_mode": "special_rule",
        "m_special": min(m, 2.0),
        "cause_tags": tags,
        "mitigation_tags": ["embankment_shelter"] if river_dist > 20 else [],
        "model_note": "Quay exposure increases with river-aligned wind.",
        "limitations": ["Near bridges/underpasses confidence is reduced."],
        "confidence_penalty": 0.1,
        "gust_sensitive": aligned > 0.6,
    }


def _score_open_space(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    enclosure = metrics.get("enclosure_ratio") or 0.3
    orientation = metrics.get("corridor_orientation_deg") or 0.0
    aligned_exit = alignment_score(wind_deg, orientation) > 0.7
    m = 1.5 if enclosure < 0.3 else 0.9
    tags = ["large_open_space"] if enclosure < 0.3 else ["enclosed_square"]
    if aligned_exit:
        m *= 1.15
        tags.append("aligned_exit_gap")
    handling = "vector_preferred" if metrics.get("nearby_highrise_score", 0) > 0.6 else "special_rule"
    if handling == "vector_preferred":
        tags.append("corner_acceleration")
    return {
        "handling_mode": handling,
        "m_special": min(m, 1.8),
        "cause_tags": tags,
        "mitigation_tags": ["surrounding_buildings"] if enclosure > 0.5 else [],
        "model_note": "Square center exposure depends on enclosure and exit alignment.",
        "limitations": [],
        "confidence_penalty": 0.2 if handling == "vector_preferred" else 0.05,
        "gust_sensitive": aligned_exit,
    }


def _score_irregular_fabric(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    curvature = metrics.get("curvature_score") or 0.5
    enclosure = metrics.get("enclosure_ratio") or 0.7
    corridor = metrics.get("corridor_orientation_deg") or 0.0
    align = alignment_score(wind_deg, corridor)
    m = 0.85 + (0.3 * align) - (0.2 * curvature)
    tags = ["irregular_fabric", "short_curved_segments"]
    if enclosure > 0.6:
        tags.append("dense_enclosure")
    if metrics.get("special_geometry_type") == "open_exit_transition":
        tags.append("open_exit_transition")
        m *= 1.2
    return {
        "handling_mode": "low_confidence" if curvature > 0.6 else "special_rule",
        "m_special": max(0.7, min(m, 1.4)),
        "cause_tags": tags,
        "mitigation_tags": ["dense_interior_shelter"] if enclosure > 0.6 else [],
        "model_note": "Irregular old-street fabric reduces alignment confidence.",
        "limitations": ["Simple corridor alignment may not represent micro-variations."],
        "confidence_penalty": 0.25,
        "gust_sensitive": False,
    }


def _score_slope(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    aspect = metrics.get("slope_aspect_deg") or 0.0
    slope = metrics.get("slope_deg") or 5.0
    windward = angle_diff_deg(wind_deg, aspect) < 45
    m = 1.3 if windward else 0.75
    tags = ["exposed_slope"] if windward else ["lee_shelter"]
    if slope > 10:
        tags.append("ridge_exposure")
    return {
        "handling_mode": "special_rule",
        "m_special": m,
        "cause_tags": tags,
        "mitigation_tags": [],
        "model_note": "Terrain modifier from slope aspect relative to wind.",
        "limitations": ["DEM placeholder — slope metrics may be approximate."],
        "confidence_penalty": 0.15,
        "gust_sensitive": windward,
    }


def _score_tunnel(
    _metrics: dict[str, Any],
    _wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    return {
        "handling_mode": "excluded",
        "m_special": 1.0,
        "cause_tags": ["covered_geometry", "interior_flow_not_modeled"],
        "mitigation_tags": [],
        "model_note": "Tunnel/underpass interior airflow is not estimated.",
        "limitations": ["Portal gust possible at entrances only."],
        "confidence_penalty": 0.5,
        "gust_sensitive": False,
    }


def _score_high_rise(
    metrics: dict[str, Any],
    wind_deg: float,
    _speed: float,
) -> dict[str, Any]:
    nearby = metrics.get("nearby_highrise_score") or 0.8
    orientation = metrics.get("corridor_orientation_deg") or 0.0
    corner = alignment_score(wind_deg, (orientation + 90) % 360) > 0.6
    m = 1.2 + (0.4 * nearby)
    tags = ["high_rise_cluster", "downwash_risk", "vector_model_preferred"]
    if corner:
        tags.append("corner_acceleration")
        m *= 1.1
    tags.append("tower_gap_channeling")
    return {
        "handling_mode": "vector_preferred",
        "m_special": min(m, 2.0),
        "cause_tags": tags,
        "mitigation_tags": [],
        "model_note": "Scalar estimate only — advanced vector model preferred.",
        "limitations": ["Downwash and corner effects are approximate."],
        "confidence_penalty": 0.3,
        "gust_sensitive": True,
    }