"""Full-area data pipeline orchestration."""

from __future__ import annotations

from typing import Any

from wind_track.config.settings import direction_set
from wind_track.db.connection import fetch_one, get_db
from wind_track.services.enrich_heights import enrich_building_heights
from wind_track.services.import_osm import import_osm_area
from wind_track.services.metrics.batch import compute_metrics_for_area
from wind_track.services.precompute import precompute_directions
from wind_track.services.priority_zones import seed_priority_zones
from wind_track.services.progress import log_step, step
from wind_track.services.quality_audit import run_quality_audit
from wind_track.services.tiles.generate import generate_area_tiles


async def run_area_pipeline(
    area_slug: str,
    *,
    force_import: bool = False,
    direction_count: int = 8,
    skip_tiles: bool = False,
) -> dict[str, Any]:
    """Run import → enrich → priority zones → metrics → precompute → audit → tiles."""
    dirs = direction_set(direction_count)
    log_step(
        "pipeline",
        area=area_slug,
        directions=len(dirs),
        force=force_import,
        skip_tiles=skip_tiles,
    )

    with step("import_osm", area=area_slug):
        import_result = await import_osm_area(area_slug, force=force_import)
        if import_result.get("skipped"):
            log_step("import skipped", streets=import_result.get("street_count", 0))
        else:
            log_step(
                "import complete",
                features=import_result.get("features_imported", 0),
                grid=import_result.get("overpass_grid", 1),
            )

    with step("enrich_heights", area=area_slug):
        enrich_result = await enrich_building_heights(area_slug, recompute_metrics=False)
        log_step(
            "heights enriched",
            bdtopo=enrich_result.get("bdtopo_updated", 0),
            quays=enrich_result.get("quays_promoted", 0),
        )

    with step("priority_zones", area=area_slug):
        priority_result = await seed_priority_zones(area_slug)
        log_step(
            "zones seeded",
            features=priority_result.get("features_added", 0),
            vector_zones=priority_result.get("vector_zones_added", 0),
            bridges=priority_result.get("bridges_detected", 0),
        )

    metrics_count = 0
    with step("compute_metrics", area=area_slug):
        if priority_result.get("features_added", 0) > 0 or import_result.get("skipped"):
            async with get_db() as conn:
                area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (area_slug,))
                dv = await fetch_one(
                    conn,
                    "SELECT id FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
                    (area["id"],),
                )
                if area and dv:
                    metrics_count = await compute_metrics_for_area(area["id"], dv["id"])
        elif not import_result.get("skipped"):
            metrics_count = import_result.get("metrics_computed", 0)
        log_step("metrics ready", count=metrics_count)

    with step("precompute", area=area_slug, directions=len(dirs)):
        precompute_result = await precompute_directions(area_slug, directions=dirs)
        log_step(
            "cache built",
            entries=precompute_result.get("entries", 0),
            features=precompute_result.get("features", 0),
        )

    tiles_result: dict[str, Any] | None = None
    if skip_tiles:
        log_step("tiles skipped")
    else:
        with step("generate_tiles", area=area_slug, directions=len(dirs)):
            tiles_result = await generate_area_tiles(area_slug, directions=dirs)
            log_step("tiles ready", ready=tiles_result.get("ready", False))

    with step("quality_audit", area=area_slug):
        audit = await run_quality_audit(area_slug)
        b = audit.get("buildings", {})
        log_step(
            "audit complete",
            buildings=b.get("count", 0),
            official_pct=round((b.get("official_height_pct", 0) or 0) * 100, 1),
        )

    log_step("pipeline finished", area=area_slug)
    return {
        "area_slug": area_slug,
        "import": import_result,
        "enrich": enrich_result,
        "priority_zones": priority_result,
        "metrics_recomputed": metrics_count,
        "precompute": precompute_result,
        "tiles": tiles_result,
        "audit": audit,
    }