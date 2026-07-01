"""Export GeoJSON NDJSON and build PMTiles via tippecanoe."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from wind_track.config.settings import settings
from wind_track.db.connection import fetch_all, get_db, loads_json
from wind_track.services.directional_cache import list_cached_directions
from wind_track.services.flow_indicators import build_indicators_for_feature
from wind_track.services.progress import log_step
from wind_track.services.scenarios import get_active_versions
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG, exposure_class_for_score

FLOW_SYMBOLS = {
    "corridor_arrow": "▸",
    "river_corridor_arrow": "▸",
    "bridge_crosswind": "⚠",
    "open_exit_transition": "△",
    "model_limited": "◆",
}

BASE_FEATURE_TYPES = frozenset({
    "street_segment", "bridge", "quay", "river", "building", "open_space", "park", "vegetation",
})


def tiles_dir_for(area_slug: str) -> Path:
    return settings.tiles_dir / area_slug


def tile_manifest(area_slug: str) -> dict[str, Any]:
    """Return which PMTiles files exist on disk."""
    root = tiles_dir_for(area_slug)
    base = root / "base.pmtiles"
    exposure: dict[str, bool] = {}
    flow: dict[str, bool] = {}
    if root.exists():
        for path in sorted(root.glob("exposure_*.pmtiles")):
            deg = path.stem.replace("exposure_", "")
            exposure[deg] = True
        for path in sorted(root.glob("flow_*.pmtiles")):
            deg = path.stem.replace("flow_", "")
            flow[deg] = True
    return {
        "ready": base.exists() and len(exposure) > 0,
        "base_pmtiles": base.exists(),
        "exposure_pmtiles": exposure,
        "flow_pmtiles": flow,
        "tiles_path": str(root),
        "tippecanoe_available": shutil.which("tippecanoe") is not None,
    }


def _write_ndjson(path: Path, features: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for feat in features:
            fh.write(json.dumps(feat, separators=(",", ":")) + "\n")
    return len(features)


def _run_tippecanoe(ndjson: Path, out_pmtiles: Path, *, layer: str) -> bool:
    tippecanoe = shutil.which("tippecanoe")
    if not tippecanoe:
        return False
    cmd = [
        tippecanoe,
        "-o", str(out_pmtiles),
        "-l", layer,
        "-zg",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--force",
        "-P",
        str(ndjson),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_pmtiles.exists()


async def _export_base_features(area_id: int) -> list[dict[str, Any]]:
    placeholders = ",".join("?" * len(BASE_FEATURE_TYPES))
    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            f"""SELECT id, feature_type, name, geom FROM spatial_features
               WHERE area_id = ? AND feature_type IN ({placeholders})""",
            (area_id, *BASE_FEATURE_TYPES),
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        geom = loads_json(row["geom"], {})
        out.append({
            "type": "Feature",
            "id": row["id"],
            "geometry": geom,
            "properties": {
                "feature_id": row["id"],
                "feature_type": row["feature_type"],
                "name": row.get("name") or "",
            },
        })
    return out


async def _export_exposure_features(
    area_slug: str,
    direction_deg: int,
) -> list[dict[str, Any]]:
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        return []
    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)

    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT c.normalized_risk_score, c.confidence, c.cause_tags_json,
                      f.id, f.feature_type, f.name, f.geom, m.handling_mode
               FROM directional_score_cache c
               JOIN spatial_features f ON f.id = c.feature_id
               JOIN computed_feature_metrics m
                 ON m.feature_id = f.id AND m.data_version_id = c.data_version_id
               WHERE c.area_id = ? AND c.data_version_id = ? AND c.model_version_id = ?
                 AND c.direction_deg = ?""",
            (area["id"], data_version["id"], model_version["id"], direction_deg),
        )

    features: list[dict[str, Any]] = []
    for row in rows:
        geom = loads_json(row["geom"], {})
        risk = row["normalized_risk_score"]
        exposure = exposure_class_for_score(risk, config)
        cause_tags = loads_json(row.get("cause_tags_json"), [])
        gust_sensitive = any("gust" in t or "crosswind" in t for t in cause_tags)
        features.append({
            "type": "Feature",
            "id": row["id"],
            "geometry": geom,
            "properties": {
                "feature_id": row["id"],
                "feature_type": row["feature_type"],
                "name": row.get("name") or "",
                "risk_score": round(risk, 1),
                "exposure_class": exposure,
                "confidence": row["confidence"],
                "handling_mode": row["handling_mode"],
                "gust_sensitive": gust_sensitive,
                "direction_deg": direction_deg,
            },
        })
    return features


async def _export_flow_features(
    area_slug: str,
    direction_deg: int,
) -> list[dict[str, Any]]:
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        return []
    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)

    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT c.normalized_risk_score, c.confidence, c.cause_tags_json, c.subscores_json,
                      f.id, f.feature_type, f.geom, m.handling_mode, m.corridor_orientation_deg
               FROM directional_score_cache c
               JOIN spatial_features f ON f.id = c.feature_id
               JOIN computed_feature_metrics m
                 ON m.feature_id = f.id AND m.data_version_id = c.data_version_id
               WHERE c.area_id = ? AND c.data_version_id = ? AND c.model_version_id = ?
                 AND c.direction_deg = ?""",
            (area["id"], data_version["id"], model_version["id"], direction_deg),
        )

    features: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        cause_tags = loads_json(row.get("cause_tags_json"), [])
        subscores = loads_json(row.get("subscores_json"), {})
        risk = row["normalized_risk_score"]
        exposure = exposure_class_for_score(risk, config)
        feat = {
            "feature_id": row["id"],
            "feature_type": row["feature_type"],
            "geom": loads_json(row["geom"], {}),
            "risk_score": risk,
            "exposure_class": exposure,
            "confidence": row["confidence"],
            "handling_mode": row["handling_mode"],
            "cause_tags": cause_tags,
            "subscores": subscores,
            "corridor_orientation_deg": row.get("corridor_orientation_deg"),
        }
        for ind in build_indicators_for_feature(feat, float(direction_deg)):
            key = (ind["feature_id"], ind["indicator_type"])
            if key in seen:
                continue
            seen.add(key)
            itype = ind["indicator_type"]
            features.append({
                "type": "Feature",
                "geometry": ind["geom"],
                "properties": {
                    "feature_id": ind["feature_id"],
                    "indicator_type": itype,
                    "flow_direction_deg": ind["flow_direction_deg"],
                    "flow_strength": ind["flow_strength"],
                    "confidence": ind["confidence"],
                    "exposure_class": ind["exposure_class"],
                    "symbol": FLOW_SYMBOLS.get(itype, "▸"),
                },
            })
    return features


async def generate_area_tiles(
    area_slug: str,
    directions: list[int] | None = None,
) -> dict[str, Any]:
    """Build base + per-direction exposure PMTiles for an area."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["area"]:
        raise ValueError(f"No area data for {area_slug}")

    dirs = directions or await list_cached_directions(area_slug)
    if not dirs:
        raise ValueError(f"No cached directions for {area_slug}")

    root = tiles_dir_for(area_slug)
    root.mkdir(parents=True, exist_ok=True)

    log_step("exporting base tiles", area=area_slug)
    base_features = await _export_base_features(versions["area"]["id"])
    base_ndjson = root / "base.ndjson"
    base_count = _write_ndjson(base_ndjson, base_features)
    log_step("running tippecanoe", layer="base", features=base_count)
    base_built = _run_tippecanoe(base_ndjson, root / "base.pmtiles", layer="base")
    log_step("base pmtiles", ok=base_built)

    exposure_built: dict[str, bool] = {}
    exposure_counts: dict[str, int] = {}
    flow_built: dict[str, bool] = {}
    flow_counts: dict[str, int] = {}
    for idx, deg in enumerate(dirs):
        log_step("exporting exposure tiles", direction=deg, progress=f"{idx + 1}/{len(dirs)}")
        feats = await _export_exposure_features(area_slug, deg)
        ndjson = root / f"exposure_{deg}.ndjson"
        exposure_counts[str(deg)] = _write_ndjson(ndjson, feats)
        out = root / f"exposure_{deg}.pmtiles"
        log_step("running tippecanoe", layer=f"exposure_{deg}", features=len(feats))
        exposure_built[str(deg)] = _run_tippecanoe(ndjson, out, layer="exposure")

        log_step("exporting flow tiles", direction=deg)
        flow_feats = await _export_flow_features(area_slug, deg)
        flow_ndjson = root / f"flow_{deg}.ndjson"
        flow_counts[str(deg)] = _write_ndjson(flow_ndjson, flow_feats)
        flow_out = root / f"flow_{deg}.pmtiles"
        log_step("running tippecanoe", layer=f"flow_{deg}", features=len(flow_feats))
        flow_built[str(deg)] = _run_tippecanoe(flow_ndjson, flow_out, layer="flow")

    manifest = tile_manifest(area_slug)
    return {
        "area_slug": area_slug,
        "base_features": base_count,
        "base_pmtiles": base_built,
        "exposure_counts": exposure_counts,
        "exposure_pmtiles": exposure_built,
        "flow_counts": flow_counts,
        "flow_pmtiles": flow_built,
        "tippecanoe_available": manifest["tippecanoe_available"],
        "ready": manifest["ready"],
    }