"""Geospatial math utilities."""

from __future__ import annotations

import json
import math
from typing import Any

from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry


def angle_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two compass bearings (0-180)."""
    diff = abs((a - b + 180) % 360 - 180)
    return diff


def alignment_score(wind_deg: float, orientation_deg: float) -> float:
    """Score 0-1 for wind alignment with corridor orientation."""
    diff = angle_diff_deg(wind_deg, orientation_deg)
    if diff <= 15:
        return 1.0
    if diff <= 45:
        return 0.75
    if diff <= 90:
        return 0.35
    return 0.1


def line_orientation_deg(geom: BaseGeometry) -> float:
    """Compute dominant line orientation in compass degrees."""
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
    elif geom.geom_type == "MultiLineString":
        longest = max(geom.geoms, key=lambda g: g.length)
        coords = list(longest.coords)
    else:
        return 0.0
    if len(coords) < 2:
        return 0.0
    x0, y0 = coords[0]
    x1, y1 = coords[-1]
    rad = math.atan2(x1 - x0, y1 - y0)
    deg = math.degrees(rad)
    return (deg + 360) % 360


def geom_from_geojson(geojson_str: str) -> BaseGeometry:
    """Parse GeoJSON geometry string to Shapely geometry."""
    data = json.loads(geojson_str)
    return shape(data)


def geojson_from_geom(geom: BaseGeometry) -> str:
    """Serialize Shapely geometry to GeoJSON string."""
    return json.dumps(mapping(geom), separators=(",", ":"))


def bbox_from_coords(coords: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Return min_x, min_y, max_x, max_y from lon/lat coords."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)


def make_line(coords: list[tuple[float, float]]) -> str:
    """Create GeoJSON LineString from lon/lat pairs."""
    return geojson_from_geom(LineString(coords))


def make_polygon(coords: list[tuple[float, float]]) -> str:
    """Create GeoJSON Polygon from lon/lat ring."""
    return geojson_from_geom(Polygon(coords))


def make_point(lon: float, lat: float) -> str:
    """Create GeoJSON Point."""
    return geojson_from_geom(Point(lon, lat))


def length_m_approx(line: BaseGeometry, lat: float) -> float:
    """Approximate line length in meters using equirectangular projection."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    if line.geom_type != "LineString":
        return 0.0
    total = 0.0
    coords = list(line.coords)
    for i in range(1, len(coords)):
        dx = (coords[i][0] - coords[i - 1][0]) * m_per_deg_lon
        dy = (coords[i][1] - coords[i - 1][1]) * m_per_deg_lat
        total += math.hypot(dx, dy)
    return total


def centroid_of(geom: BaseGeometry) -> str:
    """Return GeoJSON point centroid."""
    return geojson_from_geom(geom.centroid)


def open_fetch_by_direction(
    center_lon: float,
    center_lat: float,
    wind_dirs: list[int] | None = None,
) -> dict[str, float]:
    """Placeholder directional fetch estimates for synthetic data."""
    dirs = wind_dirs or [0, 45, 90, 135, 180, 225, 270, 315]
    return {str(d): 0.5 + 0.3 * math.sin(math.radians(d)) for d in dirs}


def feature_bounds(geom_json: str) -> tuple[float, float, float, float]:
    """Get bbox from stored geometry JSON."""
    geom = geom_from_geojson(geom_json)
    return geom.bounds  # minx, miny, maxx, maxy


def row_to_feature_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize DB row for API output."""
    return {
        "id": row["id"],
        "area_id": row["area_id"],
        "feature_type": row["feature_type"],
        "subtype": row.get("subtype"),
        "name": row.get("name"),
        "geom": json.loads(row["geom"]),
        "properties": json.loads(row.get("properties_json") or "{}"),
        "source_confidence": row.get("source_confidence", 0.8),
    }