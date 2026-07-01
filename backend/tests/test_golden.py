"""Golden scenario tests for synthetic district features."""

from wind_track.services.scoring.scalar import score_feature


def _base_metrics(**overrides):
    defaults = {
        "corridor_orientation_deg": 0,
        "orientation_deg": 0,
        "width_m": 12,
        "height_m": 20,
        "hw_ratio": 1.67,
        "enclosure_ratio": 0.7,
        "metric_confidence": 0.8,
        "handling_mode": "normal_score",
    }
    defaults.update(overrides)
    return defaults


def test_aligned_canyon_high_exposure():
    result = score_feature("street_segment", _base_metrics(), 0, 12)
    assert result["exposure_class"] in {"high", "very_high", "medium"}
    assert "wind_aligned_corridor" in result["cause_tags"]


def test_perpendicular_canyon_lower_than_aligned():
    aligned = score_feature("street_segment", _base_metrics(corridor_orientation_deg=90), 90, 10)
    perp = score_feature("street_segment", _base_metrics(corridor_orientation_deg=0), 90, 10)
    assert aligned["risk_score"] > perp["risk_score"]


def test_bridge_special_rule_tags():
    result = score_feature(
        "bridge",
        _base_metrics(river_axis_deg=80, orientation_deg=80, handling_mode="special_rule"),
        80,
        10,
    )
    assert result["handling_mode"] == "special_rule"
    assert "bridge_exposure" in result["cause_tags"]
    assert 0.1 <= result["confidence"] <= 0.95


def test_square_open_exposure():
    result = score_feature(
        "open_space",
        _base_metrics(enclosure_ratio=0.15, handling_mode="special_rule"),
        0,
        10,
    )
    assert "large_open_space" in result["cause_tags"]


def test_irregular_fabric_low_confidence():
    result = score_feature(
        "irregular_fabric_zone",
        _base_metrics(curvature_score=0.8, enclosure_ratio=0.8, handling_mode="special_rule"),
        45,
        8,
    )
    assert result["handling_mode"] in {"low_confidence", "special_rule"}
    assert "irregular_fabric" in result["cause_tags"]