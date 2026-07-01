"""Pydantic API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class AreaResponse(BaseModel):
    id: int
    slug: str
    name: str
    area_type: str
    center_lat: float
    center_lon: float
    default_zoom: float
    active: bool


class DataQualityResponse(BaseModel):
    area_id: int
    building_count: int
    official_height_coverage: float
    estimated_height_coverage: float
    fallback_height_coverage: float
    missing_height_count: int
    roads_with_inferred_width: int
    vegetation_count: int
    special_geometry_counts: dict[str, int]
    low_confidence_count: int


class ScalarScenarioRequest(BaseModel):
    area_slug: str = "pilot_presquile"
    wind_speed_ms: float = Field(ge=0, le=40)
    wind_direction_deg: float = Field(ge=0, lt=360)
    scenario_type: Literal["manual", "current_weather", "forecast"] = "manual"
    weather_observation_id: int | None = None
    wind_gust_ms: float | None = None


class ScenarioResponse(BaseModel):
    scenario_id: int
    area_slug: str
    wind_speed_ms: float
    wind_direction_deg: float
    scenario_type: str
    feature_count: int
    model_version: str
    data_version: str


class FeatureResultResponse(BaseModel):
    feature_id: int
    feature_type: str
    name: str | None
    subtype: str | None = None
    geom: dict[str, Any]
    risk_score: float
    exposure_class: str
    local_multiplier: float
    approx_local_speed_ms: float | None
    gust_sensitive: bool
    confidence: float
    handling_mode: str
    subscores: dict[str, Any]
    cause_tags: list[str]
    mitigation_tags: list[str]
    model_note: str | None
    limitations: list[str]
    cache_hit: bool | None = None
    cache_direction_deg: float | None = None


class WeatherResponse(BaseModel):
    area_id: int
    wind_speed_10m_ms: float | None
    wind_direction_10m_deg: float | None
    wind_gust_10m_ms: float | None
    timestamp: str
    source: str
    is_forecast: bool = False
    forecast_timestamp: str | None = None


class FeedbackRequest(BaseModel):
    area_id: int
    feature_id: int | None = None
    feedback_type: str
    description: str
    wind_direction_deg: float | None = None
    weather_context: dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    id: int
    status: str


class ValidationCaseResponse(BaseModel):
    id: int
    name: str
    case_type: str
    area_id: int
    wind_direction_deg: float | None
    reference_speed_ms: float | None
    sample_count: int = 0


class ValidationRunRequest(BaseModel):
    validation_case_id: int
    model_version_id: int | None = None


class ValidationMetricsResponse(BaseModel):
    validation_case_id: int
    overall_accuracy: float
    high_wind_recall: float | None
    high_wind_precision: float | None
    adjacent_class_accuracy: float
    false_negative_rate: float | None
    metrics_json: dict[str, Any]