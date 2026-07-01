"""DEM grid fetch (Open-Meteo elevation) and slope/aspect sampling."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from wind_track.config.settings import DATA_DIR
from wind_track.services.areas import AREA_DEFINITIONS, Bbox

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
BATCH_SIZE = 100


@dataclass(frozen=True)
class DemGrid:
    """Regular lat/lon elevation grid."""

    lats: list[float]
    lons: list[float]
    elevations: list[list[float]]
    source: str = "open_meteo_elevation"

    @property
    def mean_elevation(self) -> float:
        flat = [z for row in self.elevations for z in row]
        return sum(flat) / len(flat) if flat else 0.0


@dataclass(frozen=True)
class TerrainSample:
    """Terrain metrics at a point."""

    elevation_m: float
    slope_deg: float
    slope_aspect_deg: float
    relative_elevation_m: float
    terrain_class: str


def dem_cache_path(area_slug: str) -> Path:
    return DATA_DIR / "dem" / f"{area_slug}.json"


def grid_step_for_bbox(bbox: Bbox) -> float:
    """Pick grid spacing — coarser for large areas."""
    span = max(bbox.max_lon - bbox.min_lon, bbox.max_lat - bbox.min_lat)
    return 0.003 if span > 0.08 else 0.0015


def _build_grid_coords(bbox: Bbox, step: float) -> tuple[list[float], list[float]]:
    lats: list[float] = []
    lat = bbox.min_lat
    while lat <= bbox.max_lat + 1e-9:
        lats.append(round(lat, 6))
        lat += step
    lons: list[float] = []
    lon = bbox.min_lon
    while lon <= bbox.max_lon + 1e-9:
        lons.append(round(lon, 6))
        lon += step
    return lats, lons


async def _fetch_elevations(lats: list[float], lons: list[float]) -> list[float]:
    """Batch-fetch elevations for coordinate pairs."""
    pairs = [(la, lo) for la in lats for lo in lons]
    results: list[float] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(pairs), BATCH_SIZE):
            batch = pairs[i : i + BATCH_SIZE]
            lat_q = ",".join(str(p[0]) for p in batch)
            lon_q = ",".join(str(p[1]) for p in batch)
            resp = await client.get(ELEVATION_URL, params={"latitude": lat_q, "longitude": lon_q})
            resp.raise_for_status()
            data = resp.json()
            results.extend(float(z) for z in data["elevation"])
    return results


async def fetch_dem_grid(bbox: Bbox, step: float | None = None) -> DemGrid:
    """Download elevation grid for bbox."""
    step = step or grid_step_for_bbox(bbox)
    lats, lons = _build_grid_coords(bbox, step)
    flat = await _fetch_elevations(lats, lons)
    rows: list[list[float]] = []
    idx = 0
    for _ in lats:
        rows.append(flat[idx : idx + len(lons)])
        idx += len(lons)
    return DemGrid(lats=lats, lons=lons, elevations=rows)


def save_dem_grid(area_slug: str, grid: DemGrid) -> Path:
    path = dem_cache_path(area_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "lats": grid.lats,
        "lons": grid.lons,
        "elevations": grid.elevations,
        "source": grid.source,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def load_dem_grid(area_slug: str) -> DemGrid | None:
    path = dem_cache_path(area_slug)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return DemGrid(
        lats=data["lats"],
        lons=data["lons"],
        elevations=data["elevations"],
        source=data.get("source", "open_meteo_elevation"),
    )


async def load_or_fetch_dem_grid(area_slug: str, *, force: bool = False) -> DemGrid:
    """Load cached DEM or fetch from Open-Meteo."""
    if not force:
        cached = load_dem_grid(area_slug)
        if cached:
            return cached
    area = AREA_DEFINITIONS.get(area_slug)
    if not area:
        raise ValueError(f"Unknown area: {area_slug}")
    bbox: Bbox = area["bbox"]
    grid = await fetch_dem_grid(bbox)
    save_dem_grid(area_slug, grid)
    return grid


def _bilinear(grid: DemGrid, lon: float, lat: float) -> float:
    """Bilinear sample elevation at lon/lat."""
    if not grid.lats or not grid.lons:
        return 0.0
    if lat <= grid.lats[0]:
        li = 0
        lt = 0.0
    elif lat >= grid.lats[-1]:
        li = len(grid.lats) - 2
        lt = 1.0
    else:
        li = next(i for i in range(len(grid.lats) - 1) if grid.lats[i] <= lat <= grid.lats[i + 1])
        span = grid.lats[li + 1] - grid.lats[li]
        lt = (lat - grid.lats[li]) / span if span else 0.0
    if lon <= grid.lons[0]:
        lj = 0
        ln = 0.0
    elif lon >= grid.lons[-1]:
        lj = len(grid.lons) - 2
        ln = 1.0
    else:
        lj = next(j for j in range(len(grid.lons) - 1) if grid.lons[j] <= lon <= grid.lons[j + 1])
        span = grid.lons[lj + 1] - grid.lons[lj]
        ln = (lon - grid.lons[lj]) / span if span else 0.0

    z00 = grid.elevations[li][lj]
    z01 = grid.elevations[li][lj + 1]
    z10 = grid.elevations[li + 1][lj]
    z11 = grid.elevations[li + 1][lj + 1]
    z0 = z00 * (1 - ln) + z01 * ln
    z1 = z10 * (1 - ln) + z11 * ln
    return z0 * (1 - lt) + z1 * lt


def _grid_index(grid: DemGrid, lon: float, lat: float) -> tuple[int, int] | None:
    if lat < grid.lats[0] or lat > grid.lats[-1] or lon < grid.lons[0] or lon > grid.lons[-1]:
        return None
    li = min(
        range(len(grid.lats)),
        key=lambda i: abs(grid.lats[i] - lat),
    )
    lj = min(
        range(len(grid.lons)),
        key=lambda j: abs(grid.lons[j] - lon),
    )
    return li, lj


def sample_terrain(grid: DemGrid, lon: float, lat: float) -> TerrainSample:
    """Compute slope, aspect, and terrain class at a point."""
    elev = _bilinear(grid, lon, lat)
    mean = grid.mean_elevation
    dlon = (grid.lons[1] - grid.lons[0]) if len(grid.lons) > 1 else 0.001
    dlat = (grid.lats[1] - grid.lats[0]) if len(grid.lats) > 1 else 0.001
    cos_lat = math.cos(math.radians(lat))
    dx_m = dlon * 111_320 * max(cos_lat, 0.2)
    dy_m = dlat * 111_320

    z_w = _bilinear(grid, lon - dlon, lat)
    z_e = _bilinear(grid, lon + dlon, lat)
    z_s = _bilinear(grid, lon, lat - dlat)
    z_n = _bilinear(grid, lon, lat + dlat)

    dz_dx = (z_e - z_w) / (2 * dx_m) if dx_m else 0.0
    dz_dy = (z_n - z_s) / (2 * dy_m) if dy_m else 0.0
    slope_rad = math.atan(math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy))
    slope_deg = math.degrees(slope_rad)

    aspect_rad = math.atan2(dz_dx, dz_dy)
    aspect_deg = (math.degrees(aspect_rad) + 360) % 360

    terrain_class = "flat"
    idx = _grid_index(grid, lon, lat)
    if idx and slope_deg >= 2.0:
        li, lj = idx
        neighbors = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ni, nj = li + di, lj + dj
                if 0 <= ni < len(grid.lats) and 0 <= nj < len(grid.lons):
                    neighbors.append(grid.elevations[ni][nj])
        if neighbors:
            if elev >= max(neighbors) - 0.5:
                terrain_class = "ridge"
            elif elev <= min(neighbors) + 0.5:
                terrain_class = "valley"

    return TerrainSample(
        elevation_m=round(elev, 1),
        slope_deg=round(slope_deg, 2),
        slope_aspect_deg=round(aspect_deg, 1),
        relative_elevation_m=round(elev - mean, 1),
        terrain_class=terrain_class,
    )


def terrain_summary(grid: DemGrid) -> dict[str, Any]:
    """Summary stats for CLI output."""
    return {
        "source": grid.source,
        "rows": len(grid.lats),
        "cols": len(grid.lons),
        "mean_elevation_m": round(grid.mean_elevation, 1),
        "min_elevation_m": round(min(z for row in grid.elevations for z in row), 1),
        "max_elevation_m": round(max(z for row in grid.elevations for z in row), 1),
    }