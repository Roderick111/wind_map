"""OSM Overpass import pipeline."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from wind_track.config.settings import settings
from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, loads_json, utc_now
from wind_track.db.migrate import ensure_database
from wind_track.services.areas import (
    AREA_DEFINITIONS,
    AREA_VECTOR_ZONES,
    boundary_geom_for_bbox,
)
from wind_track.services.geo import centroid_of, geom_from_geojson
from wind_track.services.directional_cache import cache_status
from wind_track.services.metrics.batch import compute_metrics_for_area
from wind_track.services.osm_normalize import classify_osm_element, dedupe_features
from wind_track.services.precompute import precompute_directions
from wind_track.services.priority_zones import seed_priority_zones
from wind_track.services.overpass_fetch import fetch_overpass_merged
from wind_track.services.quay_detect import promote_quay_streets
from wind_track.services.progress import log_step
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_QUERY_TIMEOUT_SEC = 180
OVERPASS_HTTP_TIMEOUT = httpx.Timeout(30.0, read=300.0)
OVERPASS_MAX_ATTEMPTS = 3
OVERPASS_HEARTBEAT_SEC = 30
MIN_STREETS_FOR_IMPORT = 50
OVERPASS_CACHE_DIR = settings.db_path.parent / "overpass_cache"


def _overpass_cache_path(slug: str) -> Path:
    return OVERPASS_CACHE_DIR / f"{slug}.json"


def _load_overpass_cache(slug: str) -> list[dict[str, Any]] | None:
    path = _overpass_cache_path(slug)
    if not path.exists():
        return None
    log_step("loading overpass cache", path=str(path))
    return json.loads(path.read_text())


def _save_overpass_cache(slug: str, elements: list[dict[str, Any]]) -> None:
    OVERPASS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _overpass_cache_path(slug)
    path.write_text(json.dumps(elements))
    log_step("overpass cache saved", elements=len(elements), path=str(path))


def _overpass_query(bbox_str: str) -> str:
    return f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SEC}];
    (
      way["highway"]({bbox_str});
      way["waterway"]({bbox_str});
      way["bridge"="yes"]({bbox_str});
      way["man_made"="bridge"]({bbox_str});
      way["man_made"="quay"]({bbox_str});
      way["man_made"="pier"]({bbox_str});
      way["building"]({bbox_str});
      way["natural"="water"]({bbox_str});
      way["leisure"~"park|garden|square"]({bbox_str});
      way["place"="square"]({bbox_str});
      way["landuse"~"grass|recreation_ground"]({bbox_str});
    );
    out body geom;
    """


async def _overpass_post_with_heartbeat(
    client: httpx.AsyncClient,
    url: str,
    *,
    content: str,
    headers: dict[str, str],
) -> httpx.Response:
    """POST to Overpass; emit heartbeat logs while the server works (up to 5 min)."""
    host = url.split("/")[2]
    task = asyncio.create_task(
        client.post(url, content=content, headers=headers),
    )
    waited = 0
    while not task.done():
        await asyncio.sleep(OVERPASS_HEARTBEAT_SEC)
        if task.done():
            break
        waited += OVERPASS_HEARTBEAT_SEC
        log_step("overpass still waiting", host=host, waited_s=waited, max_wait_s=300)
    return await task


async def fetch_overpass(bbox_str: str) -> list[dict[str, Any]]:
    """Download OSM elements from Overpass with retries across mirrors."""
    query = _overpass_query(bbox_str)
    headers = {
        "User-Agent": "WindTrack/0.5 (urban-wind-exposure; local-dev)",
        "Accept": "application/json",
    }
    post_headers = {**headers, "Content-Type": "text/plain; charset=utf-8"}
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=OVERPASS_HTTP_TIMEOUT, follow_redirects=True) as client:
        for mirror_idx, url in enumerate(OVERPASS_ENDPOINTS):
            host = url.split("/")[2]
            if mirror_idx > 0:
                log_step("overpass mirror switch", host=host)
            for attempt in range(OVERPASS_MAX_ATTEMPTS):
                try:
                    if attempt > 0:
                        await asyncio.sleep(2 ** attempt)
                    log_step(
                        "overpass request",
                        host=host,
                        attempt=attempt + 1,
                        max_attempts=OVERPASS_MAX_ATTEMPTS,
                        bbox=bbox_str[:40],
                    )
                    resp = await _overpass_post_with_heartbeat(
                        client,
                        url,
                        content=query,
                        headers=post_headers,
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    log_step("overpass ok", host=host, elements=len(payload.get("elements", [])))
                    return payload.get("elements", [])
                except httpx.HTTPError as exc:
                    last_error = exc
                    log_step(
                        "overpass failed",
                        host=host,
                        attempt=attempt + 1,
                        error=str(exc)[:160],
                    )
    if last_error:
        raise last_error
    return []


async def area_import_status(slug: str) -> dict[str, Any]:
    """Return whether an area already has a usable OSM import."""
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (slug,))
        if not area:
            return {"imported": False, "feature_count": 0, "street_count": 0}

        counts = await fetch_all(
            conn,
            """SELECT feature_type, COUNT(*) as c FROM spatial_features
               WHERE area_id = ? GROUP BY feature_type""",
            (area["id"],),
        )
        by_type = {row["feature_type"]: row["c"] for row in counts}
        streets = by_type.get("street_segment", 0)
        dv = await fetch_one(
            conn,
            "SELECT slug, source_dataset_ids FROM data_versions "
            "WHERE area_id = ? ORDER BY id DESC LIMIT 1",
            (area["id"],),
        )
        source_type = "unknown"
        if dv:
            ids = loads_json(dv.get("source_dataset_ids"), [])
            if ids:
                sd = await fetch_one(
                    conn,
                    "SELECT source_type FROM source_datasets WHERE id = ?",
                    (ids[0],),
                )
                if sd:
                    source_type = sd["source_type"]

        return {
            "imported": streets >= MIN_STREETS_FOR_IMPORT and source_type == "osm",
            "feature_count": sum(by_type.values()),
            "street_count": streets,
            "data_version": dv["slug"] if dv else None,
            "source_type": source_type,
        }


async def import_osm_area(slug: str = "pilot_presquile", *, force: bool = False) -> dict[str, Any]:
    """Import OSM features for a configured area."""
    await ensure_database()
    if slug not in AREA_DEFINITIONS:
        raise ValueError(f"Unknown area slug: {slug}")

    status = await area_import_status(slug)
    if status["imported"] and not force:
        cache = await cache_status(slug)
        result: dict[str, Any] = {
            "skipped": True,
            "area_slug": slug,
            "message": (
                f"OSM data already present ({status['street_count']} streets). "
                "Pass --force to re-download from Overpass."
            ),
            **status,
            "cache": cache,
        }
        if not cache.get("ready"):
            result["precompute"] = await precompute_directions(slug)
        return result

    definition = AREA_DEFINITIONS[slug]
    bbox = definition["bbox"]
    now = utc_now()

    grid = 3 if slug == "lyon_full" else 1
    cached = None if force else _load_overpass_cache(slug)
    if cached is not None:
        elements = cached
        log_step("osm loaded from cache", elements=len(elements))
    else:
        log_step("downloading osm", area=slug, grid=f"{grid}x{grid}")
        elements = await fetch_overpass_merged(fetch_overpass, bbox, grid=grid)
        log_step("osm downloaded", elements=len(elements))
        _save_overpass_cache(slug, elements)
    raw_features: list[dict[str, Any]] = []
    skipped = 0
    for el in elements:
        try:
            feat = classify_osm_element(el)
            if feat:
                raw_features.append(feat)
        except (TypeError, ValueError) as exc:
            skipped += 1
            if skipped <= 5:
                log_step(
                    "osm element skipped",
                    id=el.get("id"),
                    error=str(exc)[:120],
                )
    if skipped:
        log_step("osm elements skipped total", count=skipped)
    features = dedupe_features(raw_features)
    log_step("osm classified", features=len(features))
    vector_zone_defs = AREA_VECTOR_ZONES.get(slug, [])

    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT * FROM areas WHERE slug = ?", (slug,))
        if not area:
            await conn.execute(
                """INSERT INTO areas (slug, name, area_type, boundary_geom, center_lat, center_lon,
                   default_zoom, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    slug,
                    definition["name"],
                    definition["area_type"],
                    boundary_geom_for_bbox(bbox),
                    bbox.center_lat,
                    bbox.center_lon,
                    definition["default_zoom"],
                ),
            )
            area = await fetch_one(conn, "SELECT * FROM areas WHERE slug = ?", (slug,))
        else:
            await conn.execute(
                """UPDATE areas SET name = ?, boundary_geom = ?, center_lat = ?, center_lon = ?,
                   default_zoom = ? WHERE id = ?""",
                (
                    definition["name"],
                    boundary_geom_for_bbox(bbox),
                    bbox.center_lat,
                    bbox.center_lon,
                    definition["default_zoom"],
                    area["id"],
                ),
            )

        assert area is not None
        area_id = area["id"]

        osm_source = await fetch_one(
            conn,
            "SELECT * FROM source_datasets WHERE source_type = 'osm' ORDER BY id DESC LIMIT 1",
        )
        if not osm_source:
            await conn.execute(
                """INSERT INTO source_datasets
                   (name, provider, source_type, license, attribution, version_label, downloaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "OpenStreetMap Presqu'île",
                    "OpenStreetMap contributors",
                    "osm",
                    "ODbL",
                    "© OpenStreetMap contributors",
                    "live-import",
                    now,
                ),
            )
            osm_source = await fetch_one(
                conn,
                "SELECT * FROM source_datasets WHERE source_type = 'osm' ORDER BY id DESC LIMIT 1",
            )
        assert osm_source is not None
        source_id = osm_source["id"]

        model = await fetch_one(
            conn,
            "SELECT * FROM model_versions WHERE slug = ?",
            (settings.scalar_model_slug,),
        )
        if not model:
            await conn.execute(
                """INSERT INTO model_versions (slug, model_type, semver, config_json, created_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    settings.scalar_model_slug,
                    "scalar",
                    "0.1.0",
                    dumps_json(DEFAULT_SCALAR_CONFIG),
                    now,
                    "Initial scalar model v0.1",
                ),
            )
            model = await fetch_one(
                conn,
                "SELECT * FROM model_versions WHERE slug = ?",
                (settings.scalar_model_slug,),
            )

        version_slug = f"{slug}-osm-{now[:10]}"
        await conn.execute(
            """INSERT INTO data_versions (slug, created_at, area_id, source_dataset_ids,
               pipeline_version, status, summary_json)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (
                version_slug,
                now,
                area_id,
                dumps_json([source_id]),
                settings.pipeline_version,
                dumps_json({"import": "osm", "element_count": len(elements)}),
            ),
        )
        data_version = await fetch_one(
            conn,
            "SELECT * FROM data_versions WHERE slug = ?",
            (version_slug,),
        )
        assert data_version is not None
        data_version_id = data_version["id"]

        await conn.execute("DELETE FROM scalar_results")
        await conn.execute("DELETE FROM directional_score_cache")
        await conn.execute("DELETE FROM scenario_runs")
        await conn.execute(
            "DELETE FROM computed_feature_metrics WHERE feature_id IN "
            "(SELECT id FROM spatial_features WHERE area_id = ?)",
            (area_id,),
        )
        await conn.execute(
            "DELETE FROM spatial_features_rtree WHERE id IN "
            "(SELECT id FROM spatial_features WHERE area_id = ?)",
            (area_id,),
        )
        await conn.execute("DELETE FROM spatial_features WHERE area_id = ?", (area_id,))
        await conn.execute("DELETE FROM vector_zones WHERE area_id = ?", (area_id,))

        inserted = 0
        counts: dict[str, int] = {}
        log_step("inserting features", count=len(features))
        for feat in features:
            g = geom_from_geojson(feat["geom"])
            cursor = await conn.execute(
                """INSERT INTO spatial_features
                   (area_id, source_dataset_id, source_object_id, feature_type, subtype, name,
                    geom, centroid_geom, properties_json, source_confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    area_id,
                    source_id,
                    feat["source_object_id"],
                    feat["feature_type"],
                    feat.get("subtype"),
                    feat["name"],
                    feat["geom"],
                    centroid_of(g),
                    dumps_json(feat["properties"]),
                    feat["source_confidence"],
                    now,
                    now,
                ),
            )
            fid = cursor.lastrowid
            minx, miny, maxx, maxy = g.bounds
            await conn.execute(
                "INSERT INTO spatial_features_rtree (id, min_x, max_x, min_y, max_y) "
                "VALUES (?, ?, ?, ?, ?)",
                (fid, minx, maxx, miny, maxy),
            )
            inserted += 1
            counts[feat["feature_type"]] = counts.get(feat["feature_type"], 0) + 1

        for vz in vector_zone_defs:
            await conn.execute(
                """INSERT INTO vector_zones
                   (area_id, name, zone_type, boundary_geom, priority, reason_json, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    area_id,
                    vz["name"],
                    vz["zone_type"],
                    boundary_geom_for_bbox(vz["bbox"]),
                    vz["priority"],
                    dumps_json(vz["reason"]),
                    vz["status"],
                ),
            )

    log_step("post-import", quays="promote", zones="seed", metrics="compute")
    quays_promoted = await promote_quay_streets(slug)
    priority_stats = await seed_priority_zones(slug)
    metrics_count = await compute_metrics_for_area(area_id, data_version_id)
    log_step("metrics computed", count=metrics_count)
    precompute_stats = await precompute_directions(slug)
    log_step("import precompute done", entries=precompute_stats.get("entries", 0))

    return {
        "area_id": area_id,
        "area_slug": slug,
        "data_version_id": data_version_id,
        "data_version_slug": version_slug,
        "osm_elements": len(elements),
        "features_imported": inserted,
        "feature_counts": counts,
        "metrics_computed": metrics_count,
        "vector_zones": len(vector_zone_defs),
        "precompute": precompute_stats,
        "quays_promoted": quays_promoted,
        "priority_zones": priority_stats,
        "overpass_grid": grid,
    }