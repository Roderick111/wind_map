"""IGN BD TOPO building height enrichment."""

from __future__ import annotations

from typing import Any

import httpx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from wind_track.services.areas import Bbox

BDTOPO_WFS = "https://data.geopf.fr/wfs/ows"
BDTOPO_TYPENAME = "BDTOPO_V3:batiment"
BDTOPO_PAGE_SIZE = 2000


async def fetch_bdtopo_buildings(bbox: Bbox) -> list[dict[str, Any]]:
    """Download BD TOPO building footprints with hauteur for bbox."""
    params_base = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "typeNames": BDTOPO_TYPENAME,
        "bbox": f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat},EPSG:4326",
        "outputFormat": "application/json",
    }
    features: list[dict[str, Any]] = []
    start = 0
    timeout = httpx.Timeout(30.0, read=120.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            params = {**params_base, "count": BDTOPO_PAGE_SIZE, "startIndex": start}
            resp = await client.get(BDTOPO_WFS, params=params)
            resp.raise_for_status()
            page = resp.json().get("features", [])
            if not page:
                break
            features.extend(page)
            if len(page) < BDTOPO_PAGE_SIZE:
                break
            start += BDTOPO_PAGE_SIZE
    return features


def _bdtopo_height(props: dict[str, Any]) -> float | None:
    raw = props.get("hauteur")
    if raw is None:
        return None
    try:
        h = float(raw)
    except (TypeError, ValueError):
        return None
    return h if 2.0 <= h <= 200.0 else None


def match_bdtopo_heights(
    building_centroids: list[tuple[int, Point]],
    bdtopo_features: list[dict[str, Any]],
) -> dict[int, float]:
    """Map OSM building ids to BD TOPO hauteur via centroid-in-polygon."""
    patches: list[tuple[Any, float]] = []
    for feat in bdtopo_features:
        h = _bdtopo_height(feat.get("properties") or {})
        if h is None:
            continue
        try:
            geom = shape(feat["geometry"])
        except Exception:
            continue
        patches.append((geom, h))

    if not patches:
        return {}

    tree = STRtree([p[0] for p in patches])
    out: dict[int, float] = {}
    for bid, centroid in building_centroids:
        if bid in out:
            continue
        for idx in tree.query(centroid):
            geom, h = patches[int(idx)]
            if geom.contains(centroid) or geom.distance(centroid) < 0.00002:
                out[bid] = h
                break
    return out