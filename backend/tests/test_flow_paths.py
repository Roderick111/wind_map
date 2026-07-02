"""Normalized flow path and street-flow simulation tests."""

from wind_track.services.flow_paths.normalize import (
    build_normalized_graph,
    extract_corridors,
    merge_corridors,
)
from wind_track.services.flow_paths.simulate import path_flow_direction, simulate_street_flow
from wind_track.services.geo import make_line


def _street(fid: int, name: str, coords: list[tuple[float, float]]) -> dict:
    return {
        "feature_id": fid,
        "feature_type": "street_segment",
        "name": name,
        "geom": make_line(coords),
        "confidence": 0.8,
    }


def test_merge_duplicate_named_parallel_streets():
    features = [
        _street(1, "Rue Example", [(4.8300, 45.7600), (4.8310, 45.7600)]),
        _street(2, "Rue Example", [(4.8301, 45.7601), (4.8311, 45.7601)]),
        _street(3, "Rue Example", [(4.8302, 45.7599), (4.8312, 45.7599)]),
    ]
    corridors = extract_corridors(features)
    merged = merge_corridors(corridors)
    assert len(merged) == 1


def test_build_graph_splits_intersection():
    features = [
        _street(1, "North-South", [(4.8300, 45.7600), (4.8300, 45.7610)]),
        _street(2, "East-West", [(4.8295, 45.7605), (4.8305, 45.7605)]),
    ]
    graph = build_normalized_graph(features)
    assert len(graph.paths) >= 3
    assert len(graph.node_keys) >= 1


def test_path_flow_direction_follows_downwind_along_street():
    bearing = 90.0
    assert path_flow_direction(bearing, 270.0) == 90.0
    assert path_flow_direction(bearing, 90.0) == 270.0


def test_simulation_geometry_fallback_without_cache():
    from wind_track.services.flow_paths.simulate import PathRow

    path = PathRow(
        flow_path_id=1,
        source_feature_ids=[1],
        path_type="street",
        name="Rue Test",
        geom={"type": "LineString", "coordinates": [[4.83, 45.76], [4.831, 45.76]]},
        length_m=80.0,
        bearing_deg=90.0,
        from_node_id=1,
        to_node_id=2,
        confidence=0.8,
    )
    sim = simulate_street_flow([path], {}, 90.0)[0]
    assert sim.animate is True
    assert sim.flow_strength > 0


def test_simulation_suppresses_excluded_features():
    from wind_track.services.flow_paths.simulate import PathRow

    path = PathRow(
        flow_path_id=1,
        source_feature_ids=[9],
        path_type="street",
        name="Tunnel",
        geom={"type": "LineString", "coordinates": [[4.83, 45.76], [4.831, 45.76]]},
        length_m=80.0,
        bearing_deg=90.0,
        from_node_id=1,
        to_node_id=2,
        confidence=0.8,
    )
    exposure = {
        9: {
            "risk_score": 70.0,
            "confidence": 0.8,
            "handling_mode": "excluded",
            "subscores": {"directional_alignment": 0.9},
            "cause_tags": [],
        },
    }
    sim = simulate_street_flow([path], exposure, 90.0)[0]
    assert sim.animate is False
    assert sim.flow_strength == 0.0