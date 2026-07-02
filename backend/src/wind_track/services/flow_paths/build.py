"""Persist normalized flow paths for an area."""

from __future__ import annotations

import json
from typing import Any

from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, utc_now
from wind_track.services.flow_paths.geometry import snap_key
from wind_track.services.flow_paths.normalize import (
    FlowGraph,
    build_normalized_graph,
    path_to_geojson,
)
from wind_track.services.geo import make_point
from wind_track.services.progress import log_step, step

PERSIST_LOG_EVERY = 5_000


async def load_corridor_features(area_id: int) -> list[dict[str, Any]]:
    """Load street/quay/bridge features for path normalization."""
    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT id as feature_id, feature_type, name, geom, source_confidence
               FROM spatial_features
               WHERE area_id = ?
                 AND feature_type IN (
                   'street_segment', 'quay', 'bridge', 'open_exit_transition'
                 )""",
            (area_id,),
        )
    features: list[dict[str, Any]] = []
    for row in rows:
        features.append(
            {
                "feature_id": row["feature_id"],
                "feature_type": row["feature_type"],
                "name": row.get("name"),
                "geom": json.loads(row["geom"]),
                "confidence": row.get("source_confidence", 0.7),
            },
        )
    return features


async def persist_flow_graph(area_id: int, graph: FlowGraph) -> dict[str, int]:
    """Replace stored flow paths/nodes for an area."""
    now = utc_now()
    node_total = len(graph.node_keys)
    path_total = len(graph.paths)
    log_step("persist flow graph", nodes=node_total, paths=path_total)

    async with get_db() as conn:
        await conn.execute("DELETE FROM flow_paths WHERE area_id = ?", (area_id,))
        await conn.execute("DELETE FROM flow_path_nodes WHERE area_id = ?", (area_id,))

        node_id_by_key: dict[tuple[int, int], int] = {}
        for n_idx, key in enumerate(sorted(graph.node_keys)):
            if n_idx > 0 and n_idx % PERSIST_LOG_EVERY == 0:
                log_step("persist nodes", done=n_idx, total=node_total)
            lon_lat = _key_to_lonlat(key, graph.paths)
            cur = await conn.execute(
                """INSERT INTO flow_path_nodes
                   (area_id, geom, node_type, connected_path_ids_json, created_at)
                   VALUES (?, ?, 'intersection', '[]', ?)""",
                (area_id, make_point(lon_lat[0], lon_lat[1]), now),
            )
            node_id_by_key[key] = cur.lastrowid

        path_count = 0
        for path in graph.paths:
            if path_count > 0 and path_count % PERSIST_LOG_EVERY == 0:
                log_step("persist paths", done=path_count, total=path_total)
            from_id = node_id_by_key.get(path.from_key)
            to_id = node_id_by_key.get(path.to_key)
            await conn.execute(
                """INSERT INTO flow_paths
                   (area_id, source_feature_ids_json, path_type, name, geom, length_m,
                    bearing_deg, from_node_id, to_node_id, confidence, animate, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    area_id,
                    dumps_json(path.source_feature_ids),
                    path.path_type,
                    path.name,
                    path_to_geojson(path),
                    round(path.length_m, 2),
                    round(path.bearing_deg, 2),
                    from_id,
                    to_id,
                    path.confidence,
                    now,
                ),
            )
            path_count += 1

        return {"node_count": len(node_id_by_key), "path_count": path_count}


def _key_to_lonlat(key: tuple[int, int], paths) -> tuple[float, float]:
    """Recover an approximate lon/lat for a snap key from path endpoints."""
    for path in paths:
        for coord in (path.line.coords[0], path.line.coords[-1]):
            if snap_key(coord[0], coord[1], coord[1]) == key:
                return coord[0], coord[1]
    return 0.0, 0.0


async def build_flow_paths(area_slug: str) -> dict[str, Any]:
    """Build and store normalized flow paths for an area."""
    log_step("build-flow-paths", area=area_slug, hint="progress on stderr")
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT id, slug FROM areas WHERE slug = ?", (area_slug,))
        if not area:
            raise ValueError(f"Area not found: {area_slug}")

    with step("load corridor features", area=area_slug):
        features = await load_corridor_features(area["id"])
        log_step("loaded features", count=len(features))

    with step("normalize graph", area=area_slug, features=len(features)):
        graph = build_normalized_graph(features)

    with step("persist graph", area=area_slug, paths=len(graph.paths)):
        counts = await persist_flow_graph(area["id"], graph)

    return {
        "area_slug": area_slug,
        "source_features": len(features),
        "merged_corridors": len({tuple(p.source_feature_ids) for p in graph.paths}),
        **counts,
    }