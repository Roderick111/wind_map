"""City-wide data quality audit report."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import fetch_all, fetch_one, get_db
from wind_track.services.directional_cache import cache_status, list_cached_directions
from wind_track.services.import_osm import area_import_status
from wind_track.services.tiles.generate import tile_manifest


async def run_quality_audit(area_slug: str) -> dict[str, Any]:
    """Produce a repeatable audit report for an area."""
    import_status = await area_import_status(area_slug)
    cache = await cache_status(area_slug)
    tiles = tile_manifest(area_slug)

    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id, slug, name FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            raise ValueError(f"Area not found: {area_slug}")
        area_id = area["id"]

        buildings = await fetch_all(
            conn,
            "SELECT properties_json FROM spatial_features WHERE area_id = ? AND feature_type = 'building'",
            (area_id,),
        )
        height_sources = [
            json.loads(b.get("properties_json") or "{}").get("height_source")
            for b in buildings
        ]
        official = sum(
            1 for hs in height_sources
            if hs in {"official", "osm_height", "official_file", "bdnb", "bdtopo"}
        )
        estimated = sum(1 for hs in height_sources if hs in {"osm_levels", "neighborhood_median"})
        fallback = sum(
            1 for hs in height_sources
            if hs in {"synthetic", "fallback", "fallback_default", "fallback_street"}
        )

        special_types = [
            "bridge", "quay", "tunnel", "underpass", "high_rise_cluster",
            "irregular_fabric_zone", "slope_zone", "open_space",
        ]
        special_counts: dict[str, int] = {}
        for st in special_types:
            rows = await fetch_all(
                conn,
                "SELECT COUNT(*) as c FROM spatial_features WHERE area_id = ? AND feature_type = ?",
                (area_id, st),
            )
            special_counts[st] = rows[0]["c"] if rows else 0

        vz_rows = await fetch_all(
            conn,
            "SELECT zone_type, COUNT(*) as c FROM vector_zones WHERE area_id = ? GROUP BY zone_type",
            (area_id,),
        )
        vector_zone_counts = {r["zone_type"]: r["c"] for r in vz_rows}

    total_buildings = len(buildings)
    return {
        "area_slug": area_slug,
        "area_name": area["name"],
        "import": import_status,
        "buildings": {
            "count": total_buildings,
            "official_height_pct": round(official / max(total_buildings, 1), 3),
            "estimated_height_pct": round(estimated / max(total_buildings, 1), 3),
            "fallback_height_pct": round(fallback / max(total_buildings, 1), 3),
        },
        "special_geometry": special_counts,
        "vector_zones": vector_zone_counts,
        "cache": {
            **cache,
            "cached_directions": await list_cached_directions(area_slug),
        },
        "tiles": tiles,
        "priority_checks": {
            "bridges_ok": special_counts.get("bridge", 0) >= 5,
            "quays_ok": special_counts.get("quay", 0) >= 10,
            "vieux_lyon_zone": special_counts.get("irregular_fabric_zone", 0) >= 1,
            "hills_zones": special_counts.get("slope_zone", 0) >= 2,
        },
    }