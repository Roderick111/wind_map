"""Build normalized single centerlines from raw corridor features."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from wind_track.services.flow_paths.geometry import (
    MIN_SEGMENT_M,
    bearings_parallel,
    haversine_m,
    is_endpoint,
    line_from_geojson,
    midpoint,
    path_bearing,
    points_from_intersection,
    snap_key,
    split_line_at_points,
)
from wind_track.services.geo import geojson_from_geom, length_m_approx
from wind_track.services.progress import log_step

PATH_TYPES = frozenset({"street_segment", "quay", "bridge", "open_exit_transition"})
TYPE_MAP = {
    "street_segment": "street",
    "quay": "quay",
    "bridge": "bridge",
    "open_exit_transition": "open_exit",
}
MERGE_DISTANCE_M = 28.0
MIN_LENGTH_M = 15.0
MERGE_LOG_EVERY = 2_000
SPLIT_LOG_EVERY = 500


@dataclass
class RawCorridor:
    """One source feature prepared for merging."""

    feature_id: int
    feature_type: str
    name: str | None
    line: LineString
    length_m: float
    bearing_deg: float
    midpoint: tuple[float, float]
    confidence: float = 0.7


@dataclass
class NormalizedPath:
    """Single animation-ready corridor segment."""

    source_feature_ids: list[int]
    path_type: str
    name: str | None
    line: LineString
    length_m: float
    bearing_deg: float
    confidence: float
    from_key: tuple[int, int]
    to_key: tuple[int, int]


@dataclass
class FlowGraph:
    """Normalized paths plus snapped node keys."""

    paths: list[NormalizedPath] = field(default_factory=list)
    node_keys: set[tuple[int, int]] = field(default_factory=set)


def normalize_name(name: str | None) -> str | None:
    """Return a merge-friendly street name."""
    if not name:
        return None
    cleaned = name.strip().lower()
    if cleaned.startswith("way/") or cleaned.startswith("relation/"):
        return None
    return cleaned


def extract_corridors(features: list[dict]) -> list[RawCorridor]:
    """Parse eligible spatial features into corridor lines."""
    corridors: list[RawCorridor] = []
    for feat in features:
        ftype = feat.get("feature_type", "")
        if ftype not in PATH_TYPES:
            continue
        line = line_from_geojson(feat["geom"])
        if line is None:
            continue
        lat = line.coords[0][1]
        length = length_m_approx(line, lat)
        if length < MIN_LENGTH_M:
            continue
        corridors.append(
            RawCorridor(
                feature_id=int(feat["feature_id"]),
                feature_type=ftype,
                name=feat.get("name"),
                line=line,
                length_m=length,
                bearing_deg=path_bearing(line),
                midpoint=midpoint(line),
                confidence=float(feat.get("confidence", 0.7)),
            ),
        )
    return corridors


def _should_merge(a: RawCorridor, b: RawCorridor) -> bool:
    """True when two corridors represent the same visible path."""
    na = normalize_name(a.name)
    nb = normalize_name(b.name)
    if na and nb and na == nb:
        return haversine_m(a.midpoint, b.midpoint) < 90.0
    if haversine_m(a.midpoint, b.midpoint) > MERGE_DISTANCE_M:
        return False
    return bearings_parallel(a.bearing_deg, b.bearing_deg)


def _pick_representative(group: list[RawCorridor]) -> RawCorridor:
    """Keep the longest line as the corridor representative."""
    return max(group, key=lambda c: c.length_m)


def _merge_cell(midpoint: tuple[float, float]) -> tuple[int, int]:
    """Bucket midpoints into ~80 m cells for merge candidate lookup."""
    lon, lat = midpoint
    cell_m = 80.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    return (
        round(lon * m_per_deg_lon / cell_m),
        round(lat * 111_320.0 / cell_m),
    )


def _merge_candidates(
    idx: int,
    corridors: list[RawCorridor],
    buckets: dict[tuple[int, int], list[int]],
) -> list[int]:
    """Return corridor indices that might merge with idx (same + neighbor cells)."""
    cx, cy = _merge_cell(corridors[idx].midpoint)
    out: list[int] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            out.extend(buckets.get((cx + dx, cy + dy), []))
    return out


def merge_corridors(corridors: list[RawCorridor]) -> list[RawCorridor]:
    """Merge duplicate parallel corridors into one line each."""
    n = len(corridors)
    if n == 0:
        return []
    log_step("merge corridors", corridors=n)
    parent = list(range(n))
    buckets: dict[tuple[int, int], list[int]] = {}
    for idx, corridor in enumerate(corridors):
        buckets.setdefault(_merge_cell(corridor.midpoint), []).append(idx)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_j] = root_i

    for i in range(n):
        if i > 0 and i % MERGE_LOG_EVERY == 0:
            log_step("merge progress", done=i, total=n, pct=round(100 * i / n, 1))
        for j in _merge_candidates(i, corridors, buckets):
            if j <= i:
                continue
            if _should_merge(corridors[i], corridors[j]):
                union(i, j)

    groups: dict[int, list[RawCorridor]] = {}
    for idx, corridor in enumerate(corridors):
        groups.setdefault(find(idx), []).append(corridor)

    merged = [_pick_representative(group) for group in groups.values()]
    log_step("merge done", merged=len(merged), from_corridors=n)
    return merged


def _collect_intersection_points(
    i: int,
    left: LineString,
    j: int,
    right: LineString,
    split_points: dict[int, list[Point]],
) -> None:
    """Record interior intersection points for a line pair."""
    lat = left.coords[0][1]
    inter = left.intersection(right)
    tol = MIN_SEGMENT_M / 3
    for pt in points_from_intersection(inter):
        if not is_endpoint(pt, left, tol, lat):
            split_points[i].append(pt)
        if not is_endpoint(pt, right, tol, lat):
            split_points[j].append(pt)


def split_at_intersections(lines: list[LineString]) -> list[LineString]:
    """Split lines at interior intersections."""
    n = len(lines)
    if n == 0:
        return []
    log_step("intersection scan", lines=n)
    tree = STRtree(lines)
    split_points: dict[int, list[Point]] = {i: [] for i in range(n)}
    for i, left in enumerate(lines):
        if i > 0 and i % SPLIT_LOG_EVERY == 0:
            log_step("intersection progress", done=i, total=n, pct=round(100 * i / n, 1))
        for j in tree.query(left):
            j = int(j)
            if j <= i:
                continue
            _collect_intersection_points(i, left, j, lines[j], split_points)

    segments: list[LineString] = []
    for idx, line in enumerate(lines):
        lat = line.coords[0][1]
        parts = split_line_at_points(line, split_points[idx], lat)
        if not parts and length_m_approx(line, lat) >= MIN_SEGMENT_M:
            parts = [line]
        segments.extend(parts)
    log_step("intersection split done", segments=len(segments))
    return segments


def build_normalized_graph(features: list[dict]) -> FlowGraph:
    """Normalize raw features into snapped single-line flow paths."""
    log_step("extract corridors", features=len(features))
    corridors = extract_corridors(features)
    log_step("extract done", corridors=len(corridors))
    merged = merge_corridors(corridors)
    segments = split_at_intersections([c.line for c in merged])
    log_step("build path records", segments=len(segments))
    corridor_by_line: dict[int, RawCorridor] = {id(c.line): c for c in merged}

    paths: list[NormalizedPath] = []
    node_keys: set[tuple[int, int]] = set()
    for segment in segments:
        lat = segment.coords[0][1]
        length = length_m_approx(segment, lat)
        if length < MIN_SEGMENT_M:
            continue
        source = corridor_by_line.get(id(segment))
        if source is None:
            source = min(
                merged,
                key=lambda c: haversine_m(midpoint(segment), c.midpoint),
                default=None,
            )
        if source is None:
            continue
        start = segment.coords[0]
        end = segment.coords[-1]
        from_key = snap_key(start[0], start[1], lat)
        to_key = snap_key(end[0], end[1], lat)
        node_keys.update({from_key, to_key})
        paths.append(
            NormalizedPath(
                source_feature_ids=[source.feature_id],
                path_type=TYPE_MAP.get(source.feature_type, "street"),
                name=source.name,
                line=segment,
                length_m=length,
                bearing_deg=path_bearing(segment),
                confidence=source.confidence,
                from_key=from_key,
                to_key=to_key,
            ),
        )
    log_step("graph built", paths=len(paths), nodes=len(node_keys))
    return FlowGraph(paths=paths, node_keys=node_keys)


def path_to_geojson(path: NormalizedPath) -> str:
    """Serialize normalized path geometry."""
    return geojson_from_geom(path.line)