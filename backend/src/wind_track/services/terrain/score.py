"""Terrain multiplier and cause tags from DEM-derived metrics."""

from __future__ import annotations

from typing import Any

from wind_track.services.geo import alignment_score, angle_diff_deg


def terrain_multiplier_and_tags(
    metrics: dict[str, Any],
    wind_direction_deg: float,
    cfg_mult: dict[str, float],
) -> tuple[float, list[str]]:
    """Return m_terrain and terrain cause tags."""
    slope = metrics.get("slope_deg") or 0.0
    aspect = metrics.get("slope_aspect_deg") or 0.0
    rel_elev = metrics.get("relative_elevation_m") or 0.0
    terrain_class = metrics.get("terrain_class", "flat")

    if slope < 1.0:
        return 1.0, []

    windward = angle_diff_deg(wind_direction_deg, aspect) < 45
    lee = angle_diff_deg(wind_direction_deg, (aspect + 180) % 360) < 45
    tags: list[str] = []

    if windward:
        m = 1.0 + min(0.35, slope / 30)
        tags.append("exposed_slope")
    elif lee:
        m = max(0.75, 1.0 - min(0.25, slope / 40))
        tags.append("lee_shelter")
    else:
        m = 1.0

    if terrain_class == "ridge" and rel_elev > 5:
        m = min(m * 1.15, cfg_mult["max"])
        tags.append("ridge_exposure")
    if terrain_class == "valley":
        valley_align = alignment_score(wind_direction_deg, aspect) > 0.65
        if valley_align:
            m = min(m * 1.1, cfg_mult["max"])
            tags.append("valley_channeling")

    m = max(cfg_mult["min"], min(m, cfg_mult["max"]))
    return round(m, 3), tags