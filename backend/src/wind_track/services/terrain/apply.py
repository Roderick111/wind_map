"""Apply DEM-derived terrain metrics to feature rows."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import fetch_all, get_db
from wind_track.services.geo import geom_from_geojson
from wind_track.services.terrain.dem import DemGrid, load_or_fetch_dem_grid, sample_terrain, terrain_summary

TERRAIN_FEATURE_TYPES = frozenset({
    "street_segment", "bridge", "quay", "open_space", "slope_zone", "park", "open_exit_transition",
})


async def apply_dem_metrics(
    area_slug: str,
    *,
    force_fetch: bool = False,
    recompute_precompute: bool = False,
) -> dict[str, Any]:
    """Sample DEM at feature centroids and update computed_feature_metrics."""
    grid = await load_or_fetch_dem_grid(area_slug, force=force_fetch)

    from wind_track.db.connection import fetch_one

    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            raise ValueError(f"Area not found: {area_slug}")
        area_id = area["id"]
        dv = await fetch_one(
            conn,
            "SELECT id FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
            (area_id,),
        )
        if not dv:
            raise ValueError(f"No data version for {area_slug}")
        data_version_id = dv["id"]

        placeholders = ",".join("?" * len(TERRAIN_FEATURE_TYPES))
        rows = await fetch_all(
            conn,
            f"""SELECT f.id, f.feature_type, f.geom, m.id as metric_id
               FROM spatial_features f
               JOIN computed_feature_metrics m
                 ON m.feature_id = f.id AND m.data_version_id = ?
               WHERE f.area_id = ? AND f.feature_type IN ({placeholders})""",
            (data_version_id, area_id, *TERRAIN_FEATURE_TYPES),
        )

        updated = 0
        for row in rows:
            geom = geom_from_geojson(row["geom"])
            lon, lat = geom.centroid.x, geom.centroid.y
            sample = sample_terrain(grid, lon, lat)
            await conn.execute(
                """UPDATE computed_feature_metrics
                   SET slope_deg = ?, slope_aspect_deg = ?, relative_elevation_m = ?
                   WHERE id = ?""",
                (
                    sample.slope_deg,
                    sample.slope_aspect_deg,
                    sample.relative_elevation_m,
                    row["metric_id"],
                ),
            )
            if row["feature_type"] == "slope_zone":
                props = {}
                feat = await fetch_all(
                    conn, "SELECT properties_json FROM spatial_features WHERE id = ?",
                    (row["id"],),
                )
                if feat:
                    props = json.loads(feat[0].get("properties_json") or "{}")
                props["terrain_class"] = sample.terrain_class
                props["elevation_m"] = sample.elevation_m
                props["dem_source"] = grid.source
                await conn.execute(
                    "UPDATE spatial_features SET properties_json = ? WHERE id = ?",
                    (json.dumps(props), row["id"]),
                )
            updated += 1

    result: dict[str, Any] = {
        "area_slug": area_slug,
        "features_updated": updated,
        "dem": terrain_summary(grid),
        "precompute": None,
    }
    if recompute_precompute:
        from wind_track.services.precompute import precompute_directions

        result["precompute"] = await precompute_directions(area_slug)
    return result