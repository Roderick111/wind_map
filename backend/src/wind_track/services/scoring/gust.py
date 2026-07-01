"""Weather gust boost helpers."""

from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def gust_speed_ratio(wind_speed_ms: float, wind_gust_ms: float | None) -> float | None:
    """Return gust/reference speed ratio when both are valid."""
    if wind_gust_ms is None or wind_speed_ms <= 0:
        return None
    return wind_gust_ms / wind_speed_ms


def gust_risk_boost(
    wind_speed_ms: float,
    wind_gust_ms: float | None,
    config: dict[str, Any],
) -> float:
    """Scale risk when forecast gusts exceed mean wind."""
    ratio = gust_speed_ratio(wind_speed_ms, wind_gust_ms)
    if ratio is None:
        return 1.0
    threshold = config.get("gust_ratio_threshold", 1.35)
    cap = config.get("gust_factor", 1.3)
    if ratio <= threshold:
        return 1.0
    excess = min(ratio - threshold, 0.8)
    return _clamp(1.0 + excess * (cap - 1.0) / 0.8, 1.0, cap)


def weather_gust_elevated(
    wind_speed_ms: float,
    wind_gust_ms: float | None,
    config: dict[str, Any],
) -> bool:
    """Whether regional gust forecast suggests elevated gust risk."""
    ratio = gust_speed_ratio(wind_speed_ms, wind_gust_ms)
    if ratio is None:
        return False
    return ratio >= config.get("gust_ratio_threshold", 1.35)