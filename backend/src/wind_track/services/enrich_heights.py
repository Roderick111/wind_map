"""Building height enrichment beyond OSM tags."""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import Point, shape

from wind_track.config.settings import settings
from wind_track.db.connection import (
    dumps_json,
    fetch_all,
    fetch_one,
    get_db,
    loads_json,
    utc_now,
)
from wind_track.services.areas import AREA_DEFINITIONS
from wind_track.services.bdtopo_heights import fetch_bdtopo_buildings, match_bdtopo_heights
from wind_track.services.geo import geom_from_geojson
from wind_track.services.metrics.batch import compute_metrics_for_area
from wind_track.services.precompute import precompute_directions
from wind_track.services.quay_detect import promote_quay_streets

DATA_DIR = settings.db_path.parent
HEIGHTS_DIR = DATA_DIR / "heights"
NEIGHBORHOOD_RADIUS_M = 40.0

OFFICIAL_SOURCES = frozenset({"osm_height", "official", "official_file", "bdnb"})


def _load_height_file(area_slug: str) -> list[tuple[Any, float, str]]:
    """Load optional GeoJSON height patches from data/heights/{slug}.geojson."""
    path = HEIGHTS_DIR / f"{area_slug}.geojson"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    patches: list[tuple[Any, float, str]] = []
    for feat in payload.get("features", []):
        geom = shape(feat["geometry"])
        props = feat.get("properties", {})
        height = props.get("height_m") or props.get("hauteur") or props.get("hauteur_mean")
        if height is None:
            continue
        source = props.get("height_source", "official_file")
        patches.append((geom, float(height), source))
    return patches


async def _fetch_bdtopo_matches(
    area_slug: str,
    buildings: list[dict[str, Any]],
) -> tuple[dict[int, float], int]:
    """Fetch BD TOPO footprints and match OSM building centroids."""
    if area_slug not in AREA_DEFINITIONS:
        return {}, 0
    bbox = AREA_DEFINITIONS[area_slug]["bbox"]
    try:
        bdtopo_features = await fetch_bdtopo_buildings(bbox)
    except Exception:
        return {}, 0
    centroids = [
        (b["id"], geom_from_geojson(b["geom"]).centroid)
        for b in buildings
    ]
    return match_bdtopo_heights(centroids, bdtopo_features), len(bdtopo_features)


async def enrich_building_heights(
    area_slug: str,
    *,
    recompute_metrics: bool = True,
) -> dict[str, Any]:
    """Enrich building heights from BD TOPO, file patches, and neighborhood median."""
    patches = _load_height_file(area_slug)

    async with get_db() as conn:
        area = await fetch_one_slug(conn, area_slug)
        if not area:
            raise ValueError(f"Area not found: {area_slug}")

        buildings = await fetch_all(
            conn,
            """SELECT id, geom, properties_json FROM spatial_features
               WHERE area_id = ? AND feature_type = 'building'""",
            (area["id"],),
        )
        dv = await fetch_one_data_version(conn, area["id"])
        area_id = area["id"]
        data_version_id = dv["id"] if dv else None

    bdtopo_map, bdtopo_features = await _fetch_bdtopo_matches(area_slug, buildings)

    known: list[tuple[int, Point, float]] = []
    for b in buildings:
        props = loads_json(b.get("properties_json"), {})
        src = props.get("height_source", "")
        h = props.get("height_m")
        if h and src in OFFICIAL_SOURCES | {"bdtopo"}:
            g = geom_from_geojson(b["geom"])
            known.append((b["id"], g.centroid, float(h)))

    file_updated = 0
    bdtopo_updated = 0
    neighbor_updated = 0
    now = utc_now()

    async with get_db() as conn:
        for b in buildings:
            props = loads_json(b.get("properties_json"), {})
            src = props.get("height_source", "fallback")
            if src in OFFICIAL_SOURCES:
                continue

            g = geom_from_geojson(b["geom"])
            centroid = g.centroid
            new_h: float | None = None
            new_src: str | None = None
            confidence = 0.5

            if b["id"] in bdtopo_map:
                new_h = bdtopo_map[b["id"]]
                new_src = "bdtopo"
                confidence = 0.9
            elif patches:
                for geom, height, psource in patches:
                    if geom.contains(centroid) or geom.distance(centroid) < 0.00005:
                        new_h = height
                        new_src = psource
                        confidence = 0.85
                        break

            if new_h is None and known:
                dists = [
                    (bid, centroid.distance(kpt) * 111_000)
                    for bid, kpt, _ in known
                    if centroid.distance(kpt) * 111_000 <= NEIGHBORHOOD_RADIUS_M
                ]
                if dists:
                    neighbors = sorted(dists, key=lambda x: x[1])[:5]
                    heights = [
                        h for bid, kpt, h in known
                        if any(bid == n[0] for n in neighbors)
                    ]
                    if heights:
                        new_h = sum(heights) / len(heights)
                        new_src = "neighborhood_median"
                        confidence = 0.55

            if new_h is None:
                continue

            props["height_m"] = round(new_h, 1)
            props["height_source"] = new_src
            props["height_confidence"] = confidence
            await conn.execute(
                "UPDATE spatial_features SET properties_json = ?, updated_at = ? WHERE id = ?",
                (dumps_json(props), now, b["id"]),
            )
            if new_src == "neighborhood_median":
                neighbor_updated += 1
            elif new_src == "bdtopo":
                bdtopo_updated += 1
            else:
                file_updated += 1

    quays_promoted = await promote_quay_streets(area_slug)

    metrics_count = 0
    precompute_stats: dict[str, int] | None = None
    changed = file_updated or bdtopo_updated or neighbor_updated or quays_promoted
    if recompute_metrics and data_version_id is not None:
        metrics_count = await compute_metrics_for_area(area_id, data_version_id)
        if changed:
            precompute_stats = await precompute_directions(area_slug)

    return {
        "area_slug": area_slug,
        "file_patches": len(patches),
        "bdtopo_features": bdtopo_features,
        "bdtopo_updated": bdtopo_updated,
        "file_updated": file_updated,
        "neighborhood_updated": neighbor_updated,
        "quays_promoted": quays_promoted,
        "metrics_recomputed": metrics_count,
        "precompute": precompute_stats,
    }


async def fetch_one_slug(conn: Any, slug: str) -> dict[str, Any] | None:
    return await fetch_one(conn, "SELECT * FROM areas WHERE slug = ?", (slug,))


async def fetch_one_data_version(conn: Any, area_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        "SELECT * FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
        (area_id,),
    )