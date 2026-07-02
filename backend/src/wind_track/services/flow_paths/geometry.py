"""Geometry helpers for normalized flow paths."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from wind_track.services.geo import angle_diff_deg, length_m_approx, line_orientation_deg

MIN_SEGMENT_M = 15.0
SNAP_M = 4.0


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in meters between two lon/lat points."""
    lat1, lon1 = math.radians(a[1]), math.radians(a[0])
    lat2, lon2 = math.radians(b[1]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def midpoint(line: LineString) -> tuple[float, float]:
    """Return lon/lat midpoint of a line."""
    c = line.interpolate(0.5, normalized=True)
    return c.x, c.y


def line_from_geojson(geom: dict | str) -> LineString | None:
    """Parse GeoJSON geometry to a single LineString."""
    if isinstance(geom, str):
        geom = json.loads(geom)
    gtype = geom.get("type")
    if gtype == "LineString":
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            return None
        return LineString(coords)
    if gtype == "MultiLineString":
        parts = geom.get("coordinates") or []
        if not parts:
            return None
        candidates = [LineString(part) for part in parts if len(part) >= 2]
        longest = max(
            candidates,
            key=lambda g: length_m_approx(g, g.coords[0][1]),
            default=None,
        )
        return longest
    return None


def path_bearing(line: LineString) -> float:
    """Compass bearing along line from first to last coordinate."""
    return line_orientation_deg(line)


def points_from_intersection(geom: BaseGeometry) -> list[Point]:
    """Flatten intersection geometry to points."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type == "LineString":
        return [Point(geom.coords[0]), Point(geom.coords[-1])]
    if geom.geom_type == "GeometryCollection":
        out: list[Point] = []
        for part in geom.geoms:
            out.extend(points_from_intersection(part))
        return out
    return []


def is_endpoint(pt: Point, line: LineString, tol_m: float, lat: float) -> bool:
    """True if point is near either end of the line."""
    start = (line.coords[0][0], line.coords[0][1])
    end = (line.coords[-1][0], line.coords[-1][1])
    here = (pt.x, pt.y)
    return min(haversine_m(here, start), haversine_m(here, end)) <= tol_m


def split_line_at_points(line: LineString, points: Iterable[Point], lat: float) -> list[LineString]:
    """Split a line at interior points and return valid segments."""
    if len(line.coords) < 2:
        return []

    total = length_m_approx(line, lat)
    if total <= 0:
        return []

    ratios: list[float] = []
    for pt in points:
        if is_endpoint(pt, line, SNAP_M, lat):
            continue
        ratio = line.project(pt, normalized=True)
        if (ratio * total) >= MIN_SEGMENT_M and ((1.0 - ratio) * total) >= MIN_SEGMENT_M:
            ratios.append(ratio)

    if not ratios:
        return [line] if total >= MIN_SEGMENT_M else []

    bounds = [0.0, *sorted(set(ratios)), 1.0]
    parts: list[LineString] = []
    for i in range(len(bounds) - 1):
        t0, t1 = bounds[i], bounds[i + 1]
        if (t1 - t0) * total < MIN_SEGMENT_M:
            continue
        seg = _extract_segment(line, t0, t1)
        if seg and length_m_approx(seg, lat) >= MIN_SEGMENT_M:
            parts.append(seg)
    return parts


def _extract_segment(line: LineString, t0: float, t1: float) -> LineString | None:
    """Extract a polyline substring by normalized interpolation positions."""
    if t1 <= t0:
        return None
    if t0 <= 0.0 and t1 >= 1.0:
        return line
    p0 = line.interpolate(t0, normalized=True)
    p1 = line.interpolate(t1, normalized=True)
    inner: list[tuple[float, float]] = []
    for lon, lat in line.coords:
        ratio = line.project(Point(lon, lat), normalized=True)
        if t0 < ratio < t1:
            inner.append((lon, lat))
    return LineString([(p0.x, p0.y), *inner, (p1.x, p1.y)])


def snap_key(lon: float, lat: float, lat_ref: float) -> tuple[int, int]:
    """Bucket lon/lat into a snap grid (~4 m)."""
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_ref))
    cell_lon = SNAP_M / m_per_deg_lon
    cell_lat = SNAP_M / 111_320.0
    return round(lon / cell_lon), round(lat / cell_lat)


def bearings_parallel(a: float, b: float, tol_deg: float = 25.0) -> bool:
    """True if bearings are parallel (same or opposite corridor)."""
    diff = angle_diff_deg(a, b)
    return diff <= tol_deg or diff >= 180 - tol_deg