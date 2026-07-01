"""Batch metric computation for an area."""

from __future__ import annotations

from typing import Any

from wind_track.db.connection import dumps_json, fetch_all, get_db
from wind_track.services.metrics.compute import compute_metrics_for_feature


async def compute_metrics_for_area(area_id: int, data_version_id: int) -> int:
    """Compute and upsert metrics for all features in an area."""
    async with get_db() as conn:
        await conn.execute(
            """DELETE FROM computed_feature_metrics
               WHERE data_version_id = ? AND feature_id IN (
                 SELECT id FROM spatial_features WHERE area_id = ?
               )""",
            (data_version_id, area_id),
        )
        features = await fetch_all(
            conn,
            "SELECT * FROM spatial_features WHERE area_id = ?",
            (area_id,),
        )
        count = 0
        for feat in features:
            metrics = compute_metrics_for_feature(feat)
            await conn.execute(
                """INSERT INTO computed_feature_metrics
                   (feature_id, data_version_id, metric_version, orientation_deg,
                    corridor_orientation_deg, width_m, height_m, height_source, height_confidence,
                    hw_ratio, curvature_score, enclosure_ratio, open_fetch_by_direction_json,
                    river_distance_m, river_axis_deg, vegetation_density, slope_deg,
                    slope_aspect_deg, relative_elevation_m, nearby_highrise_score,
                    special_geometry_type, handling_mode, metric_confidence, limitations_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feat["id"],
                    data_version_id,
                    "v0.1",
                    metrics.get("orientation_deg"),
                    metrics.get("corridor_orientation_deg"),
                    metrics.get("width_m"),
                    metrics.get("height_m"),
                    metrics.get("height_source"),
                    metrics.get("height_confidence"),
                    metrics.get("hw_ratio"),
                    metrics.get("curvature_score"),
                    metrics.get("enclosure_ratio"),
                    dumps_json(metrics.get("open_fetch_by_direction_json")),
                    metrics.get("river_distance_m"),
                    metrics.get("river_axis_deg"),
                    metrics.get("vegetation_density"),
                    metrics.get("slope_deg"),
                    metrics.get("slope_aspect_deg"),
                    metrics.get("relative_elevation_m"),
                    metrics.get("nearby_highrise_score"),
                    metrics.get("special_geometry_type"),
                    metrics.get("handling_mode"),
                    metrics.get("metric_confidence"),
                    dumps_json(metrics.get("limitations_json", [])),
                ),
            )
            count += 1
    return count