"""Flow indicator generation tests."""

from wind_track.services.flow_indicators import build_indicators_for_feature
from wind_track.services.geo import make_line


def test_corridor_arrow_for_aligned_street():
    geom = make_line([(4.83, 45.76), (4.831, 45.76)])
    feature = {
        "feature_id": 1,
        "feature_type": "street_segment",
        "geom": geom,
        "risk_score": 55.0,
        "exposure_class": "high",
        "confidence": 0.75,
        "handling_mode": "normal_score",
        "cause_tags": ["wind_aligned_corridor"],
        "subscores": {"directional_alignment": 0.85},
    }
    indicators = build_indicators_for_feature(feature, 90.0)
    types = {i["indicator_type"] for i in indicators}
    assert "corridor_arrow" in types


def test_bridge_crosswind_marker():
    geom = make_line([(4.83, 45.76), (4.83, 45.761)])
    feature = {
        "feature_id": 2,
        "feature_type": "bridge",
        "geom": geom,
        "risk_score": 60.0,
        "exposure_class": "high",
        "confidence": 0.7,
        "handling_mode": "special_rule",
        "cause_tags": ["bridge_exposure", "crosswind_discomfort"],
        "subscores": {},
    }
    indicators = build_indicators_for_feature(feature, 90.0)
    types = {i["indicator_type"] for i in indicators}
    assert "bridge_crosswind" in types


def test_low_confidence_suppresses_arrows():
    feature = {
        "feature_id": 3,
        "feature_type": "street_segment",
        "geom": make_line([(4.83, 45.76), (4.831, 45.76)]),
        "risk_score": 70.0,
        "exposure_class": "high",
        "confidence": 0.3,
        "handling_mode": "low_confidence",
        "cause_tags": [],
        "subscores": {"directional_alignment": 0.9},
    }
    indicators = build_indicators_for_feature(feature, 90.0)
    assert all(i["indicator_type"] == "model_limited" for i in indicators)