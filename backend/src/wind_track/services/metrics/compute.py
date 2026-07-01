"""Static feature metric computation."""

from __future__ import annotations

import json
from typing import Any

from wind_track.services.geo import (
    geom_from_geojson,
    length_m_approx,
    line_orientation_deg,
    open_fetch_by_direction,
)


def classify_handling_mode(feature_type: str, metrics: dict[str, Any]) -> str:
    """Determine handling mode from feature type and metrics."""
    if feature_type in {"tunnel", "underpass"}:
        return "excluded"
    if feature_type == "high_rise_cluster":
        return "vector_preferred"
    if feature_type in {"bridge", "quay", "open_space", "slope_zone", "irregular_fabric_zone"}:
        return "special_rule"
    if feature_type in {"covered_passage", "arcade"}:
        return "low_confidence"
    if metrics.get("metric_confidence", 1.0) < 0.4:
        return "low_confidence"
    return "normal_score"


def compute_metrics_for_feature(
    feature: dict[str, Any],
    related: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute static metrics for one spatial feature."""
    related = related or {}
    geom = geom_from_geojson(feature["geom"])
    ftype = feature["feature_type"]
    props = json.loads(feature.get("properties_json") or "{}")
    lat = geom.centroid.y

    orientation = line_orientation_deg(geom) if geom.geom_type in {"LineString", "MultiLineString"} else 0.0
    width = props.get("width_m", 12.0 if ftype == "street_segment" else None)
    height = props.get("height_m", 15.0 if ftype == "building" else None)
    hw_ratio = (height / width) if height and width and width > 0 else None

    metrics: dict[str, Any] = {
        "orientation_deg": orientation,
        "corridor_orientation_deg": props.get("corridor_orientation_deg", orientation),
        "width_m": width,
        "height_m": height,
        "height_source": props.get("height_source", "synthetic"),
        "height_confidence": props.get("height_confidence", 0.7),
        "hw_ratio": hw_ratio,
        "curvature_score": props.get("curvature_score", 0.2),
        "enclosure_ratio": props.get("enclosure_ratio", 0.5),
        "open_fetch_by_direction_json": open_fetch_by_direction(geom.centroid.x, geom.centroid.y),
        "river_distance_m": related.get("river_distance_m", props.get("river_distance_m")),
        "river_axis_deg": related.get("river_axis_deg", props.get("river_axis_deg", 90.0)),
        "vegetation_density": props.get("vegetation_density", 0.0),
        "slope_deg": props.get("slope_deg", 0.0),
        "slope_aspect_deg": props.get("slope_aspect_deg", 0.0),
        "relative_elevation_m": props.get("relative_elevation_m", 0.0),
        "nearby_highrise_score": props.get("nearby_highrise_score", 0.0),
        "special_geometry_type": props.get("special_geometry_type"),
        "metric_confidence": props.get("metric_confidence", 0.75),
        "limitations_json": props.get("limitations", []),
    }

    if ftype == "street_segment" and geom.geom_type == "LineString":
        metrics["segment_length_m"] = length_m_approx(geom, lat)

    metrics["handling_mode"] = classify_handling_mode(ftype, metrics)
    return metrics