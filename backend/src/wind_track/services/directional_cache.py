"""Read precomputed directional exposure from cache."""

from __future__ import annotations

import json
from typing import Any

from wind_track.config.settings import settings
from wind_track.db.connection import fetch_all, get_db, loads_json
from wind_track.services.geo import angle_diff_deg
from wind_track.services.scenarios import get_active_versions
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG, exposure_class_for_score
from wind_track.services.scoring.gust import gust_risk_boost, weather_gust_elevated
from wind_track.services.scoring.scalar import clamp

PRECOMPUTE_REF_SPEED_MS = 8.0


def snap_direction(direction_deg: float, available: list[int] | None = None) -> int:
    """Snap wind direction to nearest precomputed bearing."""
    dirs = available or settings.precompute_directions
    return min(dirs, key=lambda d: angle_diff_deg(direction_deg, float(d)))


def scale_risk_score(
    cached_risk: float,
    wind_speed_ms: float,
    reference_speed_ms: float = PRECOMPUTE_REF_SPEED_MS,
    config: dict[str, Any] | None = None,
) -> float:
    """Scale cached risk score from reference wind speed to target speed."""
    cfg = config or DEFAULT_SCALAR_CONFIG
    ref_cap = cfg["reference_speed_cap_ms"]
    ref_factor = clamp(reference_speed_ms / 8.0, 0.5, ref_cap / 8.0)
    new_factor = clamp(wind_speed_ms / 8.0, 0.5, ref_cap / 8.0)
    if ref_factor <= 0:
        return cached_risk
    return clamp(cached_risk * (new_factor / ref_factor), 0, 100)


async def list_cached_directions(area_slug: str) -> list[int]:
    """Return sorted direction bearings present in cache."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        return []
    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT DISTINCT direction_deg FROM directional_score_cache
               WHERE area_id = ? AND data_version_id = ? AND model_version_id = ?
               ORDER BY direction_deg""",
            (area["id"], data_version["id"], model_version["id"]),
        )
    return [int(r["direction_deg"]) for r in rows]


async def cache_status(area_slug: str) -> dict[str, Any]:
    """Return whether directional cache exists for an area."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        return {"ready": False, "entry_count": 0}

    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    async with get_db() as conn:
        row = await conn.execute_fetchall(
            """SELECT COUNT(*) FROM directional_score_cache
               WHERE area_id = ? AND data_version_id = ? AND model_version_id = ?""",
            (area["id"], data_version["id"], model_version["id"]),
        )
        count = row[0][0] if row else 0
    cached_dirs = await list_cached_directions(area_slug)
    return {
        "ready": count > 0,
        "entry_count": count,
        "directions": cached_dirs or settings.precompute_directions,
        "direction_count": len(cached_dirs),
        "reference_speed_ms": PRECOMPUTE_REF_SPEED_MS,
    }


async def get_cached_exposure(
    area_slug: str,
    direction_deg: float,
    wind_speed_ms: float,
    wind_gust_ms: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]] | None:
    """Load exposure results from directional cache; None if cache empty."""
    status = await cache_status(area_slug)
    if not status["ready"]:
        return None

    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        return None

    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)
    cached_dirs = await list_cached_directions(area_slug)
    snapped = snap_direction(direction_deg, cached_dirs or None)

    bbox_sql = ""
    bbox_params: tuple[float, ...] = ()
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_sql = """
               AND f.id IN (
                 SELECT id FROM spatial_features_rtree
                 WHERE min_x <= ? AND max_x >= ? AND min_y <= ? AND max_y >= ?
               )"""
        bbox_params = (max_lon, min_lon, max_lat, min_lat)

    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            f"""SELECT c.*, f.feature_type, f.name, f.subtype, f.geom, m.handling_mode
               FROM directional_score_cache c
               JOIN spatial_features f ON f.id = c.feature_id
               JOIN computed_feature_metrics m
                 ON m.feature_id = f.id AND m.data_version_id = c.data_version_id
               WHERE c.area_id = ? AND c.data_version_id = ? AND c.model_version_id = ?
                 AND c.direction_deg = ?{bbox_sql}""",
            (
                area["id"], data_version["id"], model_version["id"], snapped,
                *bbox_params,
            ),
        )

    if not rows:
        return None

    results: list[dict[str, Any]] = []
    for row in rows:
        cause_tags = loads_json(row.get("cause_tags_json"), [])
        multiplier = row["normalized_multiplier"]
        risk = scale_risk_score(
            row["normalized_risk_score"],
            wind_speed_ms,
            PRECOMPUTE_REF_SPEED_MS,
            config,
        )
        wx_gust = gust_risk_boost(wind_speed_ms, wind_gust_ms, config)
        if wx_gust > 1.0:
            risk = clamp(risk * wx_gust, 0, 100)
        geom_gust = any("gust" in tag or "crosswind" in tag for tag in cause_tags)
        gust_sensitive = geom_gust or weather_gust_elevated(
            wind_speed_ms, wind_gust_ms, config,
        )
        results.append({
            "feature_id": row["feature_id"],
            "feature_type": row["feature_type"],
            "name": row.get("name"),
            "subtype": row.get("subtype"),
            "geom": json.loads(row["geom"]) if isinstance(row["geom"], str) else row["geom"],
            "risk_score": round(risk, 1),
            "exposure_class": exposure_class_for_score(risk, config),
            "local_multiplier": multiplier,
            "approx_local_speed_ms": round(wind_speed_ms * multiplier, 2),
            "gust_sensitive": gust_sensitive,
            "confidence": row["confidence"],
            "handling_mode": row["handling_mode"],
            "subscores": loads_json(row.get("subscores_json"), {}),
            "cause_tags": cause_tags,
            "mitigation_tags": [],
            "model_note": None,
            "limitations": [],
            "cache_direction_deg": snapped,
            "cache_hit": True,
        })
    return results