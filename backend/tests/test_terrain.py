"""Terrain DEM and scoring tests."""

from wind_track.services.areas import LYON_FULL_BBOX, PRESQUILE_BBOX
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG
from wind_track.services.scoring.scalar import score_feature
from wind_track.services.terrain.dem import (
    MAX_GRID_POINTS,
    DemGrid,
    grid_point_count,
    grid_step_for_bbox,
    sample_terrain,
)
from wind_track.services.terrain.score import terrain_multiplier_and_tags

TERRAIN_MULT = DEFAULT_SCALAR_CONFIG["multipliers"]["terrain"]


def _hill_grid() -> DemGrid:
    lats = [45.75, 45.751, 45.752]
    lons = [4.83, 4.831, 4.832]
    elevations = [
        [200.0, 201.0, 202.0],
        [205.0, 210.0, 208.0],
        [215.0, 220.0, 218.0],
    ]
    return DemGrid(lats=lats, lons=lons, elevations=elevations)


def test_lyon_grid_step_stays_within_api_budget():
    step = grid_step_for_bbox(LYON_FULL_BBOX)
    assert grid_point_count(LYON_FULL_BBOX, step) <= MAX_GRID_POINTS
    assert step >= 0.003


def test_presquile_grid_step_is_finer():
    pilot_step = grid_step_for_bbox(PRESQUILE_BBOX)
    lyon_step = grid_step_for_bbox(LYON_FULL_BBOX)
    assert pilot_step <= lyon_step


def test_sample_terrain_computes_slope():
    grid = _hill_grid()
    sample = sample_terrain(grid, 4.831, 45.751)
    assert sample.slope_deg > 0
    assert 0 <= sample.slope_aspect_deg < 360


def test_terrain_windward_vs_lee():
    metrics = {"slope_deg": 8.0, "slope_aspect_deg": 90.0, "relative_elevation_m": 12.0}
    mult_wind, tags_wind = terrain_multiplier_and_tags(metrics, 90.0, TERRAIN_MULT)
    mult_lee, tags_lee = terrain_multiplier_and_tags(metrics, 270.0, TERRAIN_MULT)
    assert mult_wind > mult_lee
    assert "exposed_slope" in tags_wind
    assert "lee_shelter" in tags_lee


def test_score_feature_adds_terrain_tags():
    metrics = {
        "corridor_orientation_deg": 90,
        "hw_ratio": 1.0,
        "enclosure_ratio": 0.5,
        "slope_deg": 10.0,
        "slope_aspect_deg": 90.0,
        "relative_elevation_m": 15.0,
        "terrain_class": "ridge",
        "handling_mode": "normal_score",
        "metric_confidence": 0.8,
    }
    result = score_feature("street_segment", metrics, 90, 8.0)
    assert "exposed_slope" in result["cause_tags"]