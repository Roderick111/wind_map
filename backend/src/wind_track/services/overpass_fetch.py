"""Overpass download with bbox tiling for large areas."""

from __future__ import annotations

import asyncio
from typing import Any

from wind_track.services.areas import Bbox
from wind_track.services.progress import log_step


def split_bbox(bbox: Bbox, rows: int, cols: int) -> list[Bbox]:
    """Split a bbox into a rows×cols grid of sub-boxes."""
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")
    lon_step = (bbox.max_lon - bbox.min_lon) / cols
    lat_step = (bbox.max_lat - bbox.min_lat) / rows
    out: list[Bbox] = []
    for row in range(rows):
        for col in range(cols):
            min_lon = bbox.min_lon + col * lon_step
            max_lon = bbox.min_lon + (col + 1) * lon_step
            min_lat = bbox.min_lat + row * lat_step
            max_lat = bbox.min_lat + (row + 1) * lat_step
            out.append(Bbox(min_lon, min_lat, max_lon, max_lat))
    return out


async def fetch_overpass_merged(
    fetch_fn: Any,
    bbox: Bbox,
    *,
    grid: int = 1,
    pause_sec: float = 1.5,
) -> list[dict[str, Any]]:
    """Fetch OSM elements for bbox, tiling into grid×grid Overpass requests."""
    chunks = split_bbox(bbox, grid, grid) if grid > 1 else [bbox]
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    total = len(chunks)
    log_step("overpass grid", chunks=total, pause_sec=pause_sec)
    for i, chunk in enumerate(chunks):
        if i > 0:
            await asyncio.sleep(pause_sec)
        log_step(
            "overpass chunk",
            chunk=f"{i + 1}/{total}",
            bbox=chunk.overpass_str(),
        )
        elements = await fetch_fn(chunk.overpass_str())
        log_step("overpass chunk done", chunk=f"{i + 1}/{total}", elements=len(elements))
        for el in elements:
            key = (el.get("type", ""), int(el.get("id", 0)))
            if key in seen:
                continue
            seen.add(key)
            merged.append(el)
    log_step("overpass grid complete", chunks=total, unique_elements=len(merged))
    return merged