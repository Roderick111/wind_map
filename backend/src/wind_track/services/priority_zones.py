"""Seed Lyon priority zones and special geometry from area definitions."""

from __future__ import annotations

from typing import Any

from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, utc_now
from wind_track.services.areas import AREA_VECTOR_ZONES, Bbox, boundary_geom_for_bbox
from wind_track.services.geo import centroid_of, geom_from_geojson, make_polygon

PRIORITY_FEATURES: list[dict[str, Any]] = [
    {
        "name": "Vieux Lyon fabric",
        "feature_type": "irregular_fabric_zone",
        "bbox": Bbox(4.8255, 45.7585, 4.8305, 45.7635),
        "properties": {
            "curvature_score": 0.75,
            "enclosure_ratio": 0.85,
            "corridor_orientation_deg": 35,
            "handling_mode": "low_confidence",
        },
    },
    {
        "name": "Fourvière slopes",
        "feature_type": "slope_zone",
        "bbox": Bbox(4.818, 45.758, 4.828, 45.768),
        "properties": {
            "slope_deg": 14,
            "slope_aspect_deg": 200,
            "handling_mode": "special_rule",
        },
    },
    {
        "name": "Croix-Rousse slopes",
        "feature_type": "slope_zone",
        "bbox": Bbox(4.828, 45.768, 4.842, 45.778),
        "properties": {
            "slope_deg": 12,
            "slope_aspect_deg": 160,
            "handling_mode": "special_rule",
        },
    },
]

LYON_BRIDGE_ZONES: list[dict[str, Any]] = [
    {
        "name": "Pont Wilson & Rhône bridges",
        "zone_type": "river_bridge_zone",
        "status": "scalar_only",
        "priority": 4,
        "reason": {"note": "Major Rhône crossings — crosswind exposure"},
        "bbox": Bbox(4.838, 45.764, 4.848, 45.772),
    },
    {
        "name": "Pont Morand & Saône north",
        "zone_type": "river_bridge_zone",
        "status": "scalar_only",
        "priority": 5,
        "reason": {"note": "Saône bridges north Presqu'île"},
        "bbox": Bbox(4.832, 45.767, 4.838, 45.772),
    },
    {
        "name": "Vieux Lyon / Saône transition",
        "zone_type": "hill_quay_zone",
        "status": "vector_preferred",
        "priority": 6,
        "reason": {"note": "Steep Saône bank + irregular fabric"},
        "bbox": Bbox(4.824, 45.757, 4.831, 45.763),
    },
    {
        "name": "Croix-Rousse quay edge",
        "zone_type": "hill_quay_zone",
        "status": "scalar_only",
        "priority": 7,
        "reason": {"note": "Slope-to-quay transition on Saône"},
        "bbox": Bbox(4.828, 45.771, 4.836, 45.778),
    },
]


def _bbox_polygon(bbox: Bbox) -> str:
    return make_polygon([
        (bbox.min_lon, bbox.min_lat),
        (bbox.max_lon, bbox.min_lat),
        (bbox.max_lon, bbox.max_lat),
        (bbox.min_lon, bbox.max_lat),
        (bbox.min_lon, bbox.min_lat),
    ])


async def seed_priority_zones(area_slug: str) -> dict[str, int]:
    """Insert priority spatial features and vector zones for an area."""
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            return {"features_added": 0, "vector_zones_added": 0, "bridges_detected": 0}
        area_id = area["id"]
        now = utc_now()

        features_added = 0
        for spec in PRIORITY_FEATURES if area_slug == "lyon_full" else []:
            existing = await fetch_one(
                conn,
                """SELECT id FROM spatial_features
                   WHERE area_id = ? AND feature_type = ? AND name = ?""",
                (area_id, spec["feature_type"], spec["name"]),
            )
            if existing:
                continue
            geom = _bbox_polygon(spec["bbox"])
            g = geom_from_geojson(geom)
            await conn.execute(
                """INSERT INTO spatial_features
                   (area_id, source_object_id, feature_type, name, geom, centroid_geom,
                    properties_json, source_confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0.75, ?, ?)""",
                (
                    area_id,
                    f"priority/{spec['feature_type']}/{spec['name']}",
                    spec["feature_type"],
                    spec["name"],
                    geom,
                    centroid_of(g),
                    dumps_json(spec["properties"]),
                    now,
                    now,
                ),
            )
            features_added += 1

        vector_defs = list(AREA_VECTOR_ZONES.get(area_slug, []))
        if area_slug == "lyon_full":
            vector_defs = vector_defs + LYON_BRIDGE_ZONES

        vector_zones_added = 0
        for vz in vector_defs:
            existing = await fetch_one(
                conn,
                "SELECT id FROM vector_zones WHERE area_id = ? AND name = ?",
                (area_id, vz["name"]),
            )
            if existing:
                continue
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
            vector_zones_added += 1

        bridge_rows = await fetch_all(
            conn,
            "SELECT COUNT(*) as c FROM spatial_features WHERE area_id = ? AND feature_type = 'bridge'",
            (area_id,),
        )
        bridges_detected = bridge_rows[0]["c"] if bridge_rows else 0

    return {
        "features_added": features_added,
        "vector_zones_added": vector_zones_added,
        "bridges_detected": bridges_detected,
    }