"""Gust scoring tests."""

from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG
from wind_track.services.scoring.gust import gust_risk_boost, weather_gust_elevated
from wind_track.services.scoring.scalar import score_feature


def test_weather_gust_elevated_when_ratio_high():
    assert weather_gust_elevated(5.0, 8.0, DEFAULT_SCALAR_CONFIG) is True


def test_gust_boost_increases_risk():
    metrics = {
        "corridor_orientation_deg": 0,
        "hw_ratio": 1.8,
        "enclosure_ratio": 0.5,
        "handling_mode": "normal_score",
        "metric_confidence": 0.8,
    }
    calm = score_feature("street_segment", metrics, 0, 8.0, DEFAULT_SCALAR_CONFIG, wind_gust_ms=8.0)
    gusty = score_feature("street_segment", metrics, 0, 8.0, DEFAULT_SCALAR_CONFIG, wind_gust_ms=14.0)
    assert gusty["risk_score"] >= calm["risk_score"]
    assert gust_risk_boost(8.0, 14.0, DEFAULT_SCALAR_CONFIG) > 1.0