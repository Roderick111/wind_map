"""Convert Overpass OSM elements to spatial features."""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import LineString

from wind_track.services.geo import make_line, make_polygon
from wind_track.services.quay_detect import is_quay_street

STREET_WIDTHS: dict[str, float] = {
    "motorway": 20,
    "trunk": 18,
    "primary": 14,
    "secondary": 12,
    "tertiary": 10,
    "residential": 8,
    "unclassified": 8,
    "living_street": 7,
    "pedestrian": 12,
    "footway": 4,
    "service": 5,
}


def _coords_from_geometry(element: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = element.get("geometry") or []
    return [(pt["lon"], pt["lat"]) for pt in geometry if "lon" in pt and "lat" in pt]


def _building_height(tags: dict[str, str]) -> tuple[float, str, float]:
    if "height" in tags:
        raw = tags["height"].replace("m", "").strip()
        try:
            return float(raw), "osm_height", 0.85
        except ValueError:
            pass
    if "building:height" in tags:
        try:
            return float(tags["building:height"].replace("m", "").strip()), "osm_height", 0.85
        except ValueError:
            pass
    if "building:levels" in tags:
        try:
            levels = float(tags["building:levels"])
            return levels * 3.0, "osm_levels", 0.65
        except ValueError:
            pass
    return 12.0, "fallback_default", 0.45


def classify_osm_element(element: dict[str, Any]) -> dict[str, Any] | None:
    """Map one Overpass element to a spatial feature dict, or None to skip."""
    tags = element.get("tags") or {}
    coords = _coords_from_geometry(element)
    if len(coords) < 2 and element.get("type") != "node":
        return None

    osm_id = f"{element.get('type', 'unknown')}/{element.get('id', 0)}"
    name = tags.get("name") or tags.get("ref") or osm_id

    if tags.get("tunnel") == "yes" and tags.get("highway"):
        if len(coords) < 2:
            return None
        return _feature(
            "tunnel", name, make_line(coords), tags,
            {"width_m": float(tags["width"]) if tags.get("width") else 8},
            subtype=tags.get("highway"),
            osm_id=osm_id,
        )

    if tags.get("bridge") == "yes" or tags.get("man_made") == "bridge":
        if len(coords) < 2:
            return None
        return _feature("bridge", name, make_line(coords), tags, {"width_m": 20}, osm_id=osm_id)

    waterway = tags.get("waterway")
    if waterway in {"river", "canal", "dock", "fairway", "stream"}:
        if len(coords) < 2:
            return None
        return _feature(
            "river", name, make_line(coords), tags,
            {"river_axis_deg": _line_bearing(coords)},
            subtype=waterway,
            osm_id=osm_id,
        )

    if tags.get("natural") == "water" or tags.get("water"):
        if len(coords) < 4:
            return None
        ring = _close_ring(coords)
        if len(ring) < 4:
            return None
        return _feature("river", name, make_polygon(ring), tags, {}, subtype="water_polygon", osm_id=osm_id)

    if tags.get("building"):
        ring = _close_ring(coords)
        if len(ring) < 4:
            return None
        height, source, conf = _building_height(tags)
        return _feature(
            "building", name, make_polygon(ring), tags,
            {"height_m": height, "height_source": source, "height_confidence": conf},
            subtype=tags.get("building"),
            osm_id=osm_id,
        )

    if tags.get("leisure") in {"park", "garden"} or tags.get("landuse") in {"grass", "recreation_ground"}:
        ring = _close_ring(coords)
        if len(ring) < 4:
            return None
        density = 0.5 if tags.get("leisure") == "park" else 0.25
        return _feature(
            "park" if tags.get("leisure") == "park" else "vegetation",
            name, make_polygon(ring), tags,
            {"vegetation_density": density, "enclosure_ratio": 0.15},
            osm_id=osm_id,
        )

    if tags.get("place") == "square" or tags.get("leisure") == "square":
        ring = _close_ring(coords)
        if len(ring) < 4:
            return None
        return _feature(
            "open_space", name, make_polygon(ring), tags,
            {"enclosure_ratio": 0.2},
            subtype="square",
            osm_id=osm_id,
        )

    highway = tags.get("highway")
    if highway:
        if len(coords) < 2:
            return None
        if is_quay_street(name, tags):
            return _feature(
                "quay", name, make_line(coords), tags,
                {"river_distance_m": 3, "width_m": 10},
                subtype=highway,
                osm_id=osm_id,
            )
        width = STREET_WIDTHS.get(highway, 8)
        if tags.get("width"):
            try:
                width = float(str(tags["width"]).replace("m", "").strip())
            except ValueError:
                pass
        return _feature(
            "street_segment", name, make_line(coords), tags,
            {
                "width_m": width,
                "height_m": 18,
                "height_source": "fallback_street",
                "enclosure_ratio": 0.65,
            },
            subtype=highway,
            osm_id=osm_id,
        )

    return None


def _feature(
    feature_type: str,
    name: str,
    geom_json: str,
    tags: dict[str, str],
    props: dict[str, Any],
    subtype: str | None = None,
    osm_id: str = "",
) -> dict[str, Any]:
    merged = {**props, "osm_tags": tags}
    return {
        "feature_type": feature_type,
        "subtype": subtype,
        "name": name,
        "geom": geom_json,
        "source_object_id": osm_id,
        "properties": merged,
        "source_confidence": 0.8,
    }


def _close_ring(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not coords:
        return []
    if coords[0] != coords[-1]:
        return [*coords, coords[0]]
    return coords


def _line_bearing(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 2:
        return 0.0
    LineString(coords)
    x0, y0 = coords[0]
    x1, y1 = coords[-1]
    rad = math.atan2(x1 - x0, y1 - y0)
    return (math.degrees(rad) + 360) % 360


def dedupe_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate OSM ids."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for feat in features:
        key = feat.get("source_object_id", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(feat)
    return out