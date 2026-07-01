"""CLI commands for migrations and data pipelines."""

from __future__ import annotations

import asyncio
import json
import sys

from wind_track.config.settings import direction_set
from wind_track.db.connection import fetch_one, get_db
from wind_track.db.migrate import run_migrations
from wind_track.services.enrich_heights import enrich_building_heights
from wind_track.services.import_osm import import_osm_area
from wind_track.services.metrics.batch import compute_metrics_for_area
from wind_track.services.pipeline import run_area_pipeline
from wind_track.services.precompute import precompute_directions as run_precompute
from wind_track.services.quality_audit import run_quality_audit
from wind_track.services.seed import seed_database
from wind_track.services.tiles.generate import generate_area_tiles
from wind_track.services.validation.run import run_validation_case, seed_presquile_validation_case


def _parse_direction_count(argv: list[str]) -> tuple[list[str], int]:
    """Extract --directions N from argv."""
    count = 8
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--directions" and i + 1 < len(argv):
            count = int(argv[i + 1])
            i += 2
            continue
        cleaned.append(argv[i])
        i += 1
    return cleaned, count


def migrate() -> None:
    asyncio.run(run_migrations())
    print("Migrations applied.")


def seed() -> None:
    result = asyncio.run(seed_database())
    print(f"Seeded: {result}")


def compute_metrics() -> None:
    area_slug = sys.argv[1] if len(sys.argv) > 1 else "pilot_presquile"

    async def _run() -> int:
        async with get_db() as conn:
            area = await fetch_one(conn, "SELECT * FROM areas WHERE slug = ?", (area_slug,))
            if not area:
                raise ValueError(f"Area not found: {area_slug}")
            dv = await fetch_one(
                conn,
                "SELECT * FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
                (area["id"],),
            )
            if not dv:
                raise ValueError(f"No data version for {area_slug}")
            return await compute_metrics_for_area(area["id"], dv["id"])

    count = asyncio.run(_run())
    print(f"Computed metrics for {count} features.")


def import_osm() -> None:
    argv = [a for a in sys.argv[1:] if a not in ("--force", "--skip-if-present")]
    force = "--force" in sys.argv[1:]
    area_slug = argv[0] if argv else "pilot_presquile"
    result = asyncio.run(import_osm_area(area_slug, force=force))
    label = "OSM import skipped" if result.get("skipped") else "OSM import complete"
    print(f"{label}: {json.dumps(result, indent=2)}")


def precompute_directions() -> None:
    argv, dir_count = _parse_direction_count(sys.argv[1:])
    area = argv[0] if argv else "pilot_presquile"
    dirs = direction_set(dir_count)
    result = asyncio.run(run_precompute(area, directions=dirs))
    print(f"Precomputed ({len(dirs)} directions): {result}")


def enrich_heights() -> None:
    area = sys.argv[1] if len(sys.argv) > 1 else "pilot_presquile"
    result = asyncio.run(enrich_building_heights(area))
    print(f"Height enrichment: {json.dumps(result, indent=2)}")


def validate() -> None:
    area = sys.argv[1] if len(sys.argv) > 1 else "pilot_presquile"

    async def _run() -> dict:
        seeded = await seed_presquile_validation_case(area)
        return await run_validation_case(seeded["validation_case_id"])

    result = asyncio.run(_run())
    print(f"Validation: {json.dumps(result, indent=2)}")


def audit() -> None:
    area = sys.argv[1] if len(sys.argv) > 1 else "pilot_presquile"
    result = asyncio.run(run_quality_audit(area))
    print(json.dumps(result, indent=2))


def generate_tiles() -> None:
    argv, dir_count = _parse_direction_count(sys.argv[1:])
    area = argv[0] if argv else "pilot_presquile"
    dirs = direction_set(dir_count)
    result = asyncio.run(generate_area_tiles(area, directions=dirs))
    print(json.dumps(result, indent=2))


def pipeline() -> None:
    from wind_track.services.progress import log_step

    argv = [a for a in sys.argv[1:] if a not in ("--force", "--skip-tiles")]
    force = "--force" in sys.argv[1:]
    skip_tiles = "--skip-tiles" in sys.argv[1:]
    cleaned, dir_count = _parse_direction_count(argv)
    area = cleaned[0] if cleaned else "pilot_presquile"
    log_step(
        "wind-track-pipeline",
        area=area,
        directions=dir_count,
        hint="progress logs on stderr; final JSON on stdout",
    )
    result = asyncio.run(
        run_area_pipeline(
            area,
            force_import=force,
            direction_count=dir_count,
            skip_tiles=skip_tiles,
        ),
    )
    print(json.dumps(result, indent=2), flush=True)