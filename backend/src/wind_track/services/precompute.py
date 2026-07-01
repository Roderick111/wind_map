"""Directional score precomputation."""

from __future__ import annotations

from wind_track.config.settings import settings
from wind_track.db.connection import dumps_json, fetch_all, get_db, loads_json, utc_now
from wind_track.services.scenarios import get_active_versions
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG
from wind_track.services.scoring.scalar import score_feature


async def precompute_directions(
    area_slug: str,
    directions: list[int] | None = None,
    reference_speed_ms: float = 8.0,
) -> dict[str, int]:
    """Precompute normalized scores for fixed wind directions."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        raise ValueError(f"No active versions for area {area_slug}")

    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)
    dirs = directions or settings.precompute_directions
    now = utc_now()
    count = 0

    async with get_db() as conn:
        features = await fetch_all(
            conn,
            """SELECT f.id, f.feature_type, m.*
               FROM spatial_features f
               JOIN computed_feature_metrics m ON m.feature_id = f.id
               WHERE f.area_id = ? AND m.data_version_id = ?""",
            (area["id"], data_version["id"]),
        )

        for direction in dirs:
            for feat in features:
                metrics = {
                    "orientation_deg": feat.get("orientation_deg"),
                    "corridor_orientation_deg": feat.get("corridor_orientation_deg"),
                    "width_m": feat.get("width_m"),
                    "height_m": feat.get("height_m"),
                    "hw_ratio": feat.get("hw_ratio"),
                    "curvature_score": feat.get("curvature_score"),
                    "enclosure_ratio": feat.get("enclosure_ratio"),
                    "river_distance_m": feat.get("river_distance_m"),
                    "river_axis_deg": feat.get("river_axis_deg"),
                    "vegetation_density": feat.get("vegetation_density"),
                    "slope_deg": feat.get("slope_deg"),
                    "slope_aspect_deg": feat.get("slope_aspect_deg"),
                    "nearby_highrise_score": feat.get("nearby_highrise_score"),
                    "special_geometry_type": feat.get("special_geometry_type"),
                    "handling_mode": feat.get("handling_mode"),
                    "metric_confidence": feat.get("metric_confidence"),
                }
                result = score_feature(
                    feat["feature_type"],
                    metrics,
                    float(direction),
                    reference_speed_ms,
                    config,
                )
                await conn.execute(
                    """INSERT INTO directional_score_cache
                       (area_id, feature_id, data_version_id, model_version_id, direction_deg,
                        normalized_multiplier, normalized_risk_score, confidence,
                        subscores_json, cause_tags_json, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(feature_id, data_version_id, model_version_id, direction_deg)
                       DO UPDATE SET
                         normalized_multiplier = excluded.normalized_multiplier,
                         normalized_risk_score = excluded.normalized_risk_score,
                         confidence = excluded.confidence,
                         subscores_json = excluded.subscores_json,
                         cause_tags_json = excluded.cause_tags_json,
                         updated_at = excluded.updated_at""",
                    (
                        area["id"], feat["id"], data_version["id"], model_version["id"],
                        direction, result["local_multiplier"], result["risk_score"],
                        result["confidence"], dumps_json(result["subscores"]),
                        dumps_json(result["cause_tags"]), now,
                    ),
                )
                count += 1

    return {"directions": len(dirs), "features": len(features), "entries": count}