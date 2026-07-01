"""Scoring engine unit tests."""


from wind_track.services.geo import alignment_score, angle_diff_deg
from wind_track.services.scoring.scalar import score_feature


def test_angle_diff_deg():
    assert angle_diff_deg(10, 20) == 10
    assert angle_diff_deg(350, 10) == 20


def test_alignment_score():
    assert alignment_score(0, 0) == 1.0
    assert alignment_score(0, 90) == 0.35


def test_bridge_special_rule():
    metrics = {
        "orientation_deg": 80,
        "river_axis_deg": 80,
        "nearby_highrise_score": 0.0,
        "handling_mode": "special_rule",
        "metric_confidence": 0.8,
    }
    result = score_feature("bridge", metrics, 80, 10)
    assert result["handling_mode"] == "special_rule"
    assert "bridge_exposure" in result["cause_tags"]
    assert result["risk_score"] > 25


def test_tunnel_excluded():
    metrics = {"handling_mode": "excluded", "metric_confidence": 0.3}
    result = score_feature("tunnel", metrics, 180, 10)
    assert result["handling_mode"] == "excluded"
    assert result["risk_score"] == 0.0


def test_high_rise_vector_preferred():
    metrics = {
        "corridor_orientation_deg": 0,
        "nearby_highrise_score": 0.95,
        "enclosure_ratio": 0.4,
        "handling_mode": "vector_preferred",
        "metric_confidence": 0.6,
    }
    result = score_feature("high_rise_cluster", metrics, 90, 12)
    assert result["handling_mode"] == "vector_preferred"
    assert "vector_model_preferred" in result["cause_tags"]
    assert result["confidence"] < 0.7


def test_quay_river_aligned():
    metrics = {
        "river_axis_deg": 80,
        "river_distance_m": 5,
        "handling_mode": "special_rule",
        "metric_confidence": 0.75,
    }
    result = score_feature("quay", metrics, 80, 8)
    assert "quay_exposure" in result["cause_tags"]
    assert result["gust_sensitive"] is True