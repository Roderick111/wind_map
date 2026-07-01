"""Vector-zone export packages for advanced model research."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import fetch_all, fetch_one, get_db, loads_json


async def export_vector_zone(area_id: int, zone_id: int) -> dict[str, Any]:
    """Export buildings, streets, and zone metadata for a vector zone."""
    async with get_db() as conn:
        zone = await fetch_one(
            conn,
            "SELECT * FROM vector_zones WHERE id = ? AND area_id = ?",
            (zone_id, area_id),
        )
        if not zone:
            raise ValueError(f"Vector zone {zone_id} not found for area {area_id}")

        boundary = loads_json(zone["boundary_geom"], {})
        bbox = _bbox_from_geojson(boundary)
        if not bbox:
            raise ValueError("Invalid zone boundary")

        min_lon, min_lat, max_lon, max_lat = bbox
        features = await fetch_all(
            conn,
            """SELECT id, feature_type, name, geom, properties_json
               FROM spatial_features
               WHERE area_id = ?
                 AND feature_type IN ('building', 'street_segment', 'vegetation', 'river')
                 AND json_extract(geom, '$.coordinates[0][0]') BETWEEN ? AND ?""",
            (area_id, min_lon, max_lon),
        )
        # Filter by centroid in bbox (approximate)
        selected = []
        for feat in features:
            geom = loads_json(feat["geom"], {})
            coords = _first_coord(geom)
            if coords and min_lon <= coords[0] <= max_lon and min_lat <= coords[1] <= max_lat:
                selected.append({
                    "id": feat["id"],
                    "feature_type": feat["feature_type"],
                    "name": feat.get("name"),
                    "geom": geom,
                    "properties": loads_json(feat.get("properties_json"), {}),
                })

        area = await fetch_one(conn, "SELECT slug, name FROM areas WHERE id = ?", (area_id,))
        return {
            "format": "wind_track_vector_zone_v1",
            "area": area,
            "zone": {
                "id": zone["id"],
                "name": zone["name"],
                "zone_type": zone["zone_type"],
                "status": zone["status"],
                "priority": zone["priority"],
                "reason": loads_json(zone.get("reason_json"), {}),
                "boundary": boundary,
            },
            "feature_count": len(selected),
            "features": selected,
            "scenario_template": {
                "reference_speed_ms": 8.0,
                "directions_deg": [0, 45, 90, 135, 180, 225, 270, 315],
                "note": "Scalar screening only — vector model not bundled",
            },
        }


def _first_coord(geom: dict[str, Any]) -> list[float] | None:
    coords = geom.get("coordinates")
    if not coords:
        return None
    if geom.get("type") == "Point":
        return coords
    if geom.get("type") == "LineString":
        return coords[0]
    if geom.get("type") == "Polygon":
        return coords[0][0] if coords and coords[0] else None
    return None


def _bbox_from_geojson(geom: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if geom.get("type") != "Polygon":
        return None
    ring = geom.get("coordinates", [[]])[0]
    if not ring:
        return None
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return min(lons), min(lats), max(lons), max(lats)