"""Scenario run orchestration."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, loads_json, utc_now
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG
from wind_track.services.scoring.scalar import score_feature


async def get_active_versions(area_slug: str) -> dict[str, Any] | None:
    """Resolve area, data version, and model version."""
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT * FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            return None
        data_version = await fetch_one(
            conn,
            "SELECT * FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
            (area["id"],),
        )
        model_version = await fetch_one(
            conn,
            "SELECT * FROM model_versions WHERE slug LIKE 'scalar%' ORDER BY id DESC LIMIT 1",
        )
        return {"area": area, "data_version": data_version, "model_version": model_version}


async def run_scalar_scenario(
    area_slug: str,
    wind_speed_ms: float,
    wind_direction_deg: float,
    scenario_type: str = "manual",
    weather_observation_id: int | None = None,
    wind_gust_ms: float | None = None,
) -> dict[str, Any]:
    """Create scenario run and compute scalar results for all features."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["data_version"] or not versions["model_version"]:
        raise ValueError(f"No active versions for area {area_slug}")

    area = versions["area"]
    data_version = versions["data_version"]
    model_version = versions["model_version"]
    config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)
    now = utc_now()

    async with get_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO scenario_runs
               (area_id, data_version_id, model_version_id, scenario_type,
                reference_wind_speed_ms, reference_wind_direction_deg, wind_gust_ms,
                weather_observation_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)""",
            (
                area["id"], data_version["id"], model_version["id"],
                scenario_type, wind_speed_ms, wind_direction_deg, wind_gust_ms,
                weather_observation_id, now,
            ),
        )
        scenario_id = cursor.lastrowid

        features = await fetch_all(
            conn,
            """SELECT f.*, m.*
               FROM spatial_features f
               JOIN computed_feature_metrics m ON m.feature_id = f.id
               WHERE f.area_id = ? AND m.data_version_id = ?""",
            (area["id"], data_version["id"]),
        )

        results: list[dict[str, Any]] = []
        for feat in features:
            metrics = _metrics_from_row(feat)
            result = score_feature(
                feat["feature_type"],
                metrics,
                wind_direction_deg,
                wind_speed_ms,
                config,
                wind_gust_ms,
            )
            await conn.execute(
                """INSERT INTO scalar_results
                   (scenario_run_id, feature_id, risk_score, exposure_class, local_multiplier,
                    approx_local_speed_ms, gust_sensitive, confidence, handling_mode,
                    subscores_json, cause_tags_json, mitigation_tags_json, model_note, limitations_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scenario_id, feat["id"], result["risk_score"], result["exposure_class"],
                    result["local_multiplier"], result["approx_local_speed_ms"],
                    1 if result["gust_sensitive"] else 0,
                    result["confidence"], result["handling_mode"],
                    dumps_json(result["subscores"]),
                    dumps_json(result["cause_tags"]),
                    dumps_json(result["mitigation_tags"]),
                    result["model_note"],
                    dumps_json(result["limitations"]),
                ),
            )
            results.append({"feature_id": feat["id"], **result})

        await conn.execute(
            """UPDATE scenario_runs SET status = 'completed', completed_at = ?,
               summary_json = ? WHERE id = ?""",
            (utc_now(), dumps_json({"feature_count": len(results)}), scenario_id),
        )

    return {
        "scenario_id": scenario_id,
        "area_slug": area_slug,
        "wind_speed_ms": wind_speed_ms,
        "wind_direction_deg": wind_direction_deg,
        "scenario_type": scenario_type,
        "feature_count": len(results),
        "model_version": model_version["slug"],
        "data_version": data_version["slug"],
    }


async def get_scenario_results(
    scenario_id: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Fetch scenario results, optionally filtered by bbox."""
    async with get_db() as conn:
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            rows = await fetch_all(
                conn,
                """SELECT r.*, f.feature_type, f.name, f.geom, f.subtype
                   FROM scalar_results r
                   JOIN spatial_features f ON f.id = r.feature_id
                   JOIN spatial_features_rtree idx ON idx.id = f.id
                   WHERE r.scenario_run_id = ?
                     AND idx.max_x >= ? AND idx.min_x <= ?
                     AND idx.max_y >= ? AND idx.min_y <= ?""",
                (scenario_id, min_lon, max_lon, min_lat, max_lat),
            )
        else:
            rows = await fetch_all(
                conn,
                """SELECT r.*, f.feature_type, f.name, f.geom, f.subtype
                   FROM scalar_results r
                   JOIN spatial_features f ON f.id = r.feature_id
                   WHERE r.scenario_run_id = ?""",
                (scenario_id,),
            )
        return [_format_result(row) for row in rows]


async def get_feature_explanation(feature_id: int, scenario_id: int) -> dict[str, Any] | None:
    """Get explanation for a feature in a scenario."""
    async with get_db() as conn:
        row = await fetch_one(
            conn,
            """SELECT r.*, f.feature_type, f.name, f.subtype, f.properties_json
               FROM scalar_results r
               JOIN spatial_features f ON f.id = r.feature_id
               WHERE r.feature_id = ? AND r.scenario_run_id = ?""",
            (feature_id, scenario_id),
        )
        if not row:
            return None
        return _format_result(row)


def _metrics_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "orientation_deg": row.get("orientation_deg"),
        "corridor_orientation_deg": row.get("corridor_orientation_deg"),
        "width_m": row.get("width_m"),
        "height_m": row.get("height_m"),
        "hw_ratio": row.get("hw_ratio"),
        "curvature_score": row.get("curvature_score"),
        "enclosure_ratio": row.get("enclosure_ratio"),
        "river_distance_m": row.get("river_distance_m"),
        "river_axis_deg": row.get("river_axis_deg"),
        "vegetation_density": row.get("vegetation_density"),
        "slope_deg": row.get("slope_deg"),
        "slope_aspect_deg": row.get("slope_aspect_deg"),
        "nearby_highrise_score": row.get("nearby_highrise_score"),
        "special_geometry_type": row.get("special_geometry_type"),
        "handling_mode": row.get("handling_mode"),
        "metric_confidence": row.get("metric_confidence"),
    }


def _format_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "feature_id": row["feature_id"],
        "feature_type": row["feature_type"],
        "name": row.get("name"),
        "subtype": row.get("subtype"),
        "geom": json.loads(row["geom"]) if isinstance(row["geom"], str) else row["geom"],
        "risk_score": row["risk_score"],
        "exposure_class": row["exposure_class"],
        "local_multiplier": row["local_multiplier"],
        "approx_local_speed_ms": row["approx_local_speed_ms"],
        "gust_sensitive": bool(row["gust_sensitive"]),
        "confidence": row["confidence"],
        "handling_mode": row["handling_mode"],
        "subscores": loads_json(row.get("subscores_json"), {}),
        "cause_tags": loads_json(row.get("cause_tags_json"), []),
        "mitigation_tags": loads_json(row.get("mitigation_tags_json"), []),
        "model_note": row.get("model_note"),
        "limitations": loads_json(row.get("limitations_json"), []),
    }