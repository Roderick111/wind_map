"""Scalar flow interpretation indicators derived from cached exposure."""

from __future__ import annotations

import json
from typing import Any

from wind_track.services.directional_cache import get_cached_exposure
from wind_track.services.geo import angle_diff_deg, geom_from_geojson

MIN_CONFIDENCE = 0.45
MIN_RISK = 38.0
CORRIDOR_TYPES = frozenset({"street_segment", "quay", "bridge", "open_exit_transition"})


def _geom_str(geom: Any) -> str:
    if isinstance(geom, str):
        return geom
    return json.dumps(geom)


def _flow_point(geom: Any) -> tuple[float, float] | None:
    geom = geom_from_geojson(_geom_str(geom))
    if geom.geom_type in {"LineString", "MultiLineString"}:
        if geom.geom_type == "LineString":
            coords = list(geom.coords)
        else:
            longest = max(geom.geoms, key=lambda g: g.length)
            coords = list(longest.coords)
        if len(coords) < 2:
            return None
        mid = coords[len(coords) // 2]
        return mid[0], mid[1]
    if geom.geom_type == "Point":
        return geom.x, geom.y
    c = geom.centroid
    return c.x, c.y


def _line_bearing(geom: Any) -> float:
    geom = geom_from_geojson(_geom_str(geom))
    if geom.geom_type == "LineString" and len(geom.coords) >= 2:
        x0, y0 = geom.coords[0]
        x1, y1 = geom.coords[-1]
        import math
        return (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360) % 360
    return 0.0


def _indicator(
    feature: dict[str, Any],
    *,
    indicator_type: str,
    flow_direction_deg: float,
    flow_strength: float,
    reason: str,
    source: str,
) -> dict[str, Any] | None:
    pt = _flow_point(feature["geom"])
    if not pt:
        return None
    return {
        "feature_id": feature["feature_id"],
        "indicator_type": indicator_type,
        "geom": {"type": "Point", "coordinates": [pt[0], pt[1]]},
        "flow_direction_deg": round(flow_direction_deg, 1),
        "flow_strength": round(flow_strength, 2),
        "confidence": feature["confidence"],
        "exposure_class": feature["exposure_class"],
        "reason": reason,
        "source": source,
        "feature_type": feature["feature_type"],
    }


def build_indicators_for_feature(
    feature: dict[str, Any],
    wind_direction_deg: float,
) -> list[dict[str, Any]]:
    """Build flow indicators for one cached exposure result."""
    out: list[dict[str, Any]] = []
    conf = feature.get("confidence") or 0.0
    risk = feature.get("risk_score") or 0.0
    handling = feature.get("handling_mode", "normal_score")
    cause_tags = feature.get("cause_tags") or []
    ftype = feature.get("feature_type", "")
    exposure = feature.get("exposure_class", "low")

    if handling in {"excluded", "vector_preferred", "low_confidence"}:
        ind = _indicator(
            feature,
            indicator_type="model_limited",
            flow_direction_deg=wind_direction_deg,
            flow_strength=0.6,
            reason=_limited_reason(handling, cause_tags),
            source="special_rule",
        )
        if ind:
            out.append(ind)
        if handling != "low_confidence":
            return out

    if conf < MIN_CONFIDENCE:
        return out

    subscores = feature.get("subscores") or {}
    align = subscores.get("directional_alignment") or 0.0
    orientation = subscores.get("corridor_orientation_deg")
    if orientation is None:
        orientation = feature.get("corridor_orientation_deg") or _line_bearing(feature["geom"])

    if ftype == "bridge":
        bearing = _line_bearing(feature["geom"])
        crosswind = angle_diff_deg(wind_direction_deg, bearing) > 55
        if crosswind and risk >= MIN_RISK:
            ind = _indicator(
                feature,
                indicator_type="bridge_crosswind",
                flow_direction_deg=(wind_direction_deg + 90) % 360,
                flow_strength=min(1.4, 0.8 + risk / 100),
                reason="Wind crosses the bridge path — uncomfortable for pedestrians/cyclists.",
                source="special_rule",
            )
            if ind:
                out.append(ind)
        if "river_aligned_wind" in cause_tags:
            ind = _indicator(
                feature,
                indicator_type="river_corridor_arrow",
                flow_direction_deg=wind_direction_deg,
                flow_strength=min(1.3, 0.7 + align),
                reason="Wind aligns with the river corridor at this bridge.",
                source="scalar_alignment",
            )
            if ind:
                out.append(ind)
        return out

    if ftype == "quay" and ("river_aligned_wind" in cause_tags or "open_fetch" in cause_tags):
        ind = _indicator(
            feature,
            indicator_type="river_corridor_arrow",
            flow_direction_deg=wind_direction_deg,
            flow_strength=min(1.4, 0.75 + align),
            reason="Wind likely follows the river/quay corridor.",
            source="scalar_alignment",
        )
        if ind:
            out.append(ind)
        return out

    if "open_exit_transition" in cause_tags or "gust_transition" in cause_tags:
        ind = _indicator(
            feature,
            indicator_type="open_exit_transition",
            flow_direction_deg=wind_direction_deg,
            flow_strength=min(1.2, 0.6 + risk / 120),
            reason="Sheltered street opens to a more exposed quay, square, or bridge landing.",
            source="special_rule",
        )
        if ind:
            out.append(ind)

    if ftype in CORRIDOR_TYPES and align >= 0.65 and risk >= MIN_RISK and exposure != "low":
        ind = _indicator(
            feature,
            indicator_type="corridor_arrow",
            flow_direction_deg=wind_direction_deg,
            flow_strength=min(1.5, 0.5 + align * 0.6 + risk / 150),
            reason="Wind likely channels along this corridor under the selected wind.",
            source="scalar_alignment",
        )
        if ind:
            out.append(ind)

    return out


def _limited_reason(handling: str, cause_tags: list[str]) -> str:
    if handling == "excluded":
        return "Interior/covered geometry — scalar flow not modeled."
    if handling == "vector_preferred":
        return "Complex geometry — scalar flow is limited; vector model preferred."
    if "irregular_fabric" in cause_tags:
        return "Irregular old-street fabric — alignment confidence is low."
    return "Low confidence — flow direction uncertain."


async def get_flow_indicators(
    area_slug: str,
    direction_deg: float,
    wind_speed_ms: float,
    wind_gust_ms: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Return flow indicators for an area and wind scenario."""
    exposure = await get_cached_exposure(
        area_slug, direction_deg, wind_speed_ms, wind_gust_ms, bbox,
    )
    if not exposure:
        return []

    indicators: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for feat in exposure:
        feat = dict(feat)
        if isinstance(feat.get("subscores"), str):
            feat["subscores"] = json.loads(feat["subscores"])
        if isinstance(feat.get("cause_tags"), str):
            feat["cause_tags"] = json.loads(feat["cause_tags"])
        for ind in build_indicators_for_feature(feat, direction_deg):
            key = (ind["feature_id"], ind["indicator_type"])
            if key in seen:
                continue
            seen.add(key)
            indicators.append(ind)
    return indicators