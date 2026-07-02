"""Query normalized flow paths with simulated meteor parameters."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import fetch_all, fetch_one, get_db, loads_json
from wind_track.services.directional_cache import get_cached_exposure
from wind_track.services.flow_paths.simulate import PathRow, simulate_street_flow


async def flow_paths_ready(area_slug: str) -> bool:
    """True when normalized flow paths exist for an area."""
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            return False
        row = await fetch_one(
            conn,
            "SELECT COUNT(*) as c FROM flow_paths WHERE area_id = ?",
            (area["id"],),
        )
        return bool(row and row["c"] > 0)


async def get_flow_paths(
    area_slug: str,
    direction_deg: float,
    wind_speed_ms: float,
    wind_gust_ms: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Return flow paths with per-scenario animation parameters."""
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            return []
        rows = await fetch_all(
            conn,
            """SELECT id, source_feature_ids_json, path_type, name, geom, length_m,
                      bearing_deg, from_node_id, to_node_id, confidence
               FROM flow_paths WHERE area_id = ?""",
            (area["id"],),
        )

    if not rows:
        return []

    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        filtered = []
        for row in rows:
            geom = json.loads(row["geom"])
            coords = geom.get("coordinates") or []
            if not coords:
                continue
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            if max(lons) < min_lon or min(lons) > max_lon:
                continue
            if max(lats) < min_lat or min(lats) > max_lat:
                continue
            filtered.append(row)
        rows = filtered

    exposure = await get_cached_exposure(
        area_slug, direction_deg, wind_speed_ms, wind_gust_ms, bbox,
    )
    exposure_by_feature = {int(row["feature_id"]): dict(row) for row in (exposure or [])}
    for feat in exposure_by_feature.values():
        if isinstance(feat.get("subscores"), str):
            feat["subscores"] = loads_json(feat["subscores"], {})
        if isinstance(feat.get("cause_tags"), str):
            feat["cause_tags"] = loads_json(feat["cause_tags"], [])

    path_rows = [
        PathRow(
            flow_path_id=row["id"],
            source_feature_ids=loads_json(row["source_feature_ids_json"], []),
            path_type=row["path_type"],
            name=row.get("name"),
            geom=json.loads(row["geom"]),
            length_m=float(row["length_m"]),
            bearing_deg=float(row["bearing_deg"]),
            from_node_id=row.get("from_node_id"),
            to_node_id=row.get("to_node_id"),
            confidence=float(row["confidence"]),
        )
        for row in rows
    ]
    sim_rows = simulate_street_flow(path_rows, exposure_by_feature, direction_deg)
    simulated = {s.flow_path_id: s for s in sim_rows}

    out: list[dict[str, Any]] = []
    for row in rows:
        sim = simulated[row["id"]]
        out.append(
            {
                "flow_path_id": row["id"],
                "source_feature_ids": loads_json(row["source_feature_ids_json"], []),
                "path_type": row["path_type"],
                "name": row.get("name"),
                "geom": json.loads(row["geom"]),
                "length_m": float(row["length_m"]),
                "bearing_deg": float(row["bearing_deg"]),
                "confidence": sim.confidence,
                "flow_direction_deg": sim.flow_direction_deg,
                "flow_strength": sim.flow_strength,
                "meteor_density": sim.meteor_density,
                "animate": sim.animate,
                "reason": sim.reason,
            },
        )
    return out