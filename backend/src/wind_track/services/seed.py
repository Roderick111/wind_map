"""Synthetic Lyon pilot dataset seeding."""

from __future__ import annotations

from typing import Any

from wind_track.config.settings import settings
from wind_track.db.connection import dumps_json, fetch_one, get_db, utc_now
from wind_track.db.migrate import ensure_database
from wind_track.services.geo import (
    centroid_of,
    geom_from_geojson,
    make_line,
    make_point,
    make_polygon,
)
from wind_track.services.metrics.compute import compute_metrics_for_feature
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG

# Presqu'ile pilot — small synthetic district near Lyon center
CENTER_LAT, CENTER_LON = 45.7640, 4.8357


def _feature(
    area_id: int,
    source_id: int,
    feature_type: str,
    name: str,
    geom: str,
    props: dict[str, Any],
    subtype: str | None = None,
) -> dict[str, Any]:
    g = geom_from_geojson(geom)
    return {
        "area_id": area_id,
        "source_dataset_id": source_id,
        "source_object_id": f"synth-{feature_type}-{name}",
        "feature_type": feature_type,
        "subtype": subtype,
        "name": name,
        "geom": geom,
        "centroid_geom": centroid_of(g),
        "properties_json": dumps_json(props),
        "source_confidence": props.get("source_confidence", 0.85),
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


SYNTHETIC_FEATURES: list[dict[str, Any]] = []


def _build_feature_defs() -> list[dict[str, Any]]:
    """Build synthetic feature geometry definitions."""
    lon, lat = CENTER_LON, CENTER_LAT
    d = 0.002  # ~200m offset

    return [
        _feature(0, 0, "river", "Rhone segment", make_line([
            (lon - d, lat - d), (lon + d, lat - d * 0.5),
        ]), {"river_axis_deg": 80.0}),
        _feature(0, 0, "bridge", "Pont synthétique", make_line([
            (lon - d * 0.3, lat - d * 0.8), (lon + d * 0.3, lat - d * 0.6),
        ]), {"width_m": 25, "height_m": 8, "river_axis_deg": 80.0}),
        _feature(0, 0, "quay", "Quai Rhône", make_line([
            (lon - d * 0.8, lat - d * 0.7), (lon + d * 0.8, lat - d * 0.5),
        ]), {"river_distance_m": 5, "river_axis_deg": 80.0}),
        _feature(0, 0, "street_segment", "Rue alignée N-S", make_line([
            (lon, lat - d), (lon, lat + d),
        ]), {"width_m": 14, "height_m": 22, "enclosure_ratio": 0.7, "corridor_orientation_deg": 0}),
        _feature(0, 0, "street_segment", "Rue perpendiculaire E-W", make_line([
            (lon - d, lat), (lon + d, lat),
        ]), {"width_m": 10, "height_m": 18, "enclosure_ratio": 0.65, "corridor_orientation_deg": 90}),
        _feature(0, 0, "open_space", "Place Bellecour synth", make_polygon([
            (lon - d * 0.5, lat - d * 0.2), (lon + d * 0.5, lat - d * 0.2),
            (lon + d * 0.5, lat + d * 0.3), (lon - d * 0.5, lat + d * 0.3),
            (lon - d * 0.5, lat - d * 0.2),
        ]), {"enclosure_ratio": 0.2, "nearby_highrise_score": 0.3, "corridor_orientation_deg": 0}),
        _feature(0, 0, "building", "Tour Part-Dieu synth", make_polygon([
            (lon + d * 0.6, lat + d * 0.4), (lon + d * 0.75, lat + d * 0.4),
            (lon + d * 0.75, lat + d * 0.55), (lon + d * 0.6, lat + d * 0.55),
            (lon + d * 0.6, lat + d * 0.4),
        ]), {"height_m": 120, "height_source": "synthetic", "nearby_highrise_score": 0.9}),
        _feature(0, 0, "high_rise_cluster", "Cluster Part-Dieu", make_polygon([
            (lon + d * 0.5, lat + d * 0.35), (lon + d * 0.85, lat + d * 0.35),
            (lon + d * 0.85, lat + d * 0.6), (lon + d * 0.5, lat + d * 0.6),
            (lon + d * 0.5, lat + d * 0.35),
        ]), {"nearby_highrise_score": 0.95, "enclosure_ratio": 0.4}),
        _feature(0, 0, "irregular_fabric_zone", "Vieux Lyon fabric", make_polygon([
            (lon - d * 0.9, lat + d * 0.1), (lon - d * 0.4, lat + d * 0.1),
            (lon - d * 0.4, lat + d * 0.6), (lon - d * 0.9, lat + d * 0.6),
            (lon - d * 0.9, lat + d * 0.1),
        ]), {"curvature_score": 0.7, "enclosure_ratio": 0.8, "corridor_orientation_deg": 45}),
        _feature(0, 0, "slope_zone", "Fourvière slope", make_polygon([
            (lon - d * 0.6, lat + d * 0.7), (lon - d * 0.2, lat + d * 0.7),
            (lon - d * 0.2, lat + d * 0.95), (lon - d * 0.6, lat + d * 0.95),
            (lon - d * 0.6, lat + d * 0.7),
        ]), {"slope_deg": 12, "slope_aspect_deg": 180}),
        _feature(0, 0, "tunnel", "Tunnel sous-fleuve", make_line([
            (lon - d * 0.1, lat - d * 0.9), (lon + d * 0.1, lat - d * 0.85),
        ]), {"width_m": 8}),
        _feature(0, 0, "vegetation", "Parc trees", make_polygon([
            (lon + d * 0.1, lat + d * 0.1), (lon + d * 0.35, lat + d * 0.1),
            (lon + d * 0.35, lat + d * 0.3), (lon + d * 0.1, lat + d * 0.3),
            (lon + d * 0.1, lat + d * 0.1),
        ]), {"vegetation_density": 0.6}),
        _feature(0, 0, "open_exit_transition", "Sortie vers quai", make_point(lon - d * 0.2, lat - d * 0.55), {
            "river_distance_m": 8,
            "special_geometry_type": "open_exit_transition",
            "corridor_orientation_deg": 270,
        }),
    ]


VECTOR_ZONES = [
    {
        "name": "Part-Dieu",
        "zone_type": "high_rise_cluster",
        "status": "scalar_only",
        "priority": 1,
        "reason": {"note": "Tower cluster needs vector model for downwash"},
        "coords": [
            (CENTER_LON + 0.001, CENTER_LAT + 0.0007),
            (CENTER_LON + 0.0017, CENTER_LAT + 0.0007),
            (CENTER_LON + 0.0017, CENTER_LAT + 0.0012),
            (CENTER_LON + 0.001, CENTER_LAT + 0.0012),
            (CENTER_LON + 0.001, CENTER_LAT + 0.0007),
        ],
    },
    {
        "name": "Presqu'ile bridges",
        "zone_type": "river_bridge_zone",
        "status": "scalar_only",
        "priority": 2,
        "reason": {"note": "Bridge crosswind and river alignment"},
        "coords": [
            (CENTER_LON - 0.0015, CENTER_LAT - 0.0015),
            (CENTER_LON + 0.0015, CENTER_LAT - 0.0015),
            (CENTER_LON + 0.0015, CENTER_LAT - 0.0008),
            (CENTER_LON - 0.0015, CENTER_LAT - 0.0008),
            (CENTER_LON - 0.0015, CENTER_LAT - 0.0015),
        ],
    },
]


async def seed_database(clear: bool = True) -> dict[str, Any]:
    """Seed pilot area with synthetic features and model version."""
    await ensure_database()
    features = _build_feature_defs()

    async with get_db() as conn:
        if clear:
            tables = [
                "scalar_results", "directional_score_cache", "scenario_runs",
                "validation_metrics", "validation_samples", "validation_cases",
                "computed_feature_metrics", "feature_relationships",
                "spatial_features_rtree", "spatial_features",
                "vector_zones", "weather_observations",
                "user_feedback", "data_versions", "source_datasets", "areas",
                "model_versions",
            ]
            for table in tables:
                await conn.execute(f"DELETE FROM {table}")

        now = utc_now()
        await conn.execute(
            """INSERT INTO areas (slug, name, area_type, boundary_geom, center_lat, center_lon,
               default_zoom, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                "synthetic_test",
                "Synthetic Test District",
                "pilot_zone",
                make_polygon([
                    (CENTER_LON - 0.003, CENTER_LAT - 0.003),
                    (CENTER_LON + 0.003, CENTER_LAT - 0.003),
                    (CENTER_LON + 0.003, CENTER_LAT + 0.003),
                    (CENTER_LON - 0.003, CENTER_LAT + 0.003),
                    (CENTER_LON - 0.003, CENTER_LAT - 0.003),
                ]),
                CENTER_LAT,
                CENTER_LON,
                15,
            ),
        )
        area_row = await conn.execute_fetchall("SELECT id FROM areas WHERE slug = 'synthetic_test'")
        area_id = area_row[0][0]

        await conn.execute(
            """INSERT INTO source_datasets (name, provider, source_type, license, version_label)
               VALUES (?, ?, ?, ?, ?)""",
            ("Synthetic Pilot", "internal", "manual", "CC0", "synth-1"),
        )
        source_row = await conn.execute_fetchall("SELECT id FROM source_datasets LIMIT 1")
        source_id = source_row[0][0]

        await conn.execute(
            """INSERT INTO data_versions (slug, created_at, area_id, source_dataset_ids,
               pipeline_version, status, summary_json)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (
                "pilot-v1",
                now,
                area_id,
                dumps_json([source_id]),
                settings.pipeline_version,
                dumps_json({"features": len(features)}),
            ),
        )
        dv_row = await conn.execute_fetchall("SELECT id FROM data_versions LIMIT 1")
        data_version_id = dv_row[0][0]

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

        feature_ids: list[int] = []
        for feat in features:
            feat["area_id"] = area_id
            feat["source_dataset_id"] = source_id
            cursor = await conn.execute(
                """INSERT INTO spatial_features
                   (area_id, source_dataset_id, source_object_id, feature_type, subtype, name,
                    geom, centroid_geom, properties_json, source_confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feat["area_id"], feat["source_dataset_id"], feat["source_object_id"],
                    feat["feature_type"], feat.get("subtype"), feat["name"],
                    feat["geom"], feat["centroid_geom"], feat["properties_json"],
                    feat["source_confidence"], feat["created_at"], feat["updated_at"],
                ),
            )
            fid = cursor.lastrowid
            feature_ids.append(fid)
            g = geom_from_geojson(feat["geom"])
            minx, miny, maxx, maxy = g.bounds
            await conn.execute(
                "INSERT INTO spatial_features_rtree (id, min_x, max_x, min_y, max_y) VALUES (?, ?, ?, ?, ?)",
                (fid, minx, maxx, miny, maxy),
            )

        for vz in VECTOR_ZONES:
            await conn.execute(
                """INSERT INTO vector_zones
                   (area_id, name, zone_type, boundary_geom, priority, reason_json, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    area_id, vz["name"], vz["zone_type"],
                    make_polygon(vz["coords"]), vz["priority"],
                    dumps_json(vz["reason"]), vz["status"],
                ),
            )

        for fid in feature_ids:
            feat_dict = await fetch_one(
                conn, "SELECT * FROM spatial_features WHERE id = ?", (fid,),
            )
            if not feat_dict:
                continue
            metrics = compute_metrics_for_feature(feat_dict)
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
                    fid, data_version_id, "v0.1",
                    metrics.get("orientation_deg"), metrics.get("corridor_orientation_deg"),
                    metrics.get("width_m"), metrics.get("height_m"),
                    metrics.get("height_source"), metrics.get("height_confidence"),
                    metrics.get("hw_ratio"), metrics.get("curvature_score"),
                    metrics.get("enclosure_ratio"), dumps_json(metrics.get("open_fetch_by_direction_json")),
                    metrics.get("river_distance_m"), metrics.get("river_axis_deg"),
                    metrics.get("vegetation_density"), metrics.get("slope_deg"),
                    metrics.get("slope_aspect_deg"), metrics.get("relative_elevation_m"),
                    metrics.get("nearby_highrise_score"), metrics.get("special_geometry_type"),
                    metrics.get("handling_mode"), metrics.get("metric_confidence"),
                    dumps_json(metrics.get("limitations_json", [])),
                ),
            )

    return {
        "area_id": area_id,
        "data_version_id": data_version_id,
        "feature_count": len(feature_ids),
        "vector_zones": len(VECTOR_ZONES),
    }