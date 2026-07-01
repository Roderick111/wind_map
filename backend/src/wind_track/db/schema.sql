-- Wind Track v0.5 SQLite schema

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    area_type TEXT NOT NULL,
    parent_area_id INTEGER REFERENCES areas(id),
    boundary_geom TEXT,
    center_lat REAL NOT NULL,
    center_lon REAL NOT NULL,
    default_zoom REAL NOT NULL DEFAULT 14,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_type TEXT NOT NULL,
    license TEXT,
    attribution TEXT,
    source_url TEXT,
    downloaded_at TEXT,
    raw_path TEXT,
    version_label TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS data_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    source_dataset_ids TEXT NOT NULL DEFAULT '[]',
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS spatial_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    source_dataset_id INTEGER REFERENCES source_datasets(id),
    source_object_id TEXT,
    feature_type TEXT NOT NULL,
    subtype TEXT,
    name TEXT,
    geom TEXT NOT NULL,
    centroid_geom TEXT,
    properties_json TEXT NOT NULL DEFAULT '{}',
    source_confidence REAL NOT NULL DEFAULT 0.8,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS spatial_features_rtree USING rtree(
    id,
    min_x, max_x,
    min_y, max_y
);

CREATE TABLE IF NOT EXISTS feature_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_feature_id INTEGER NOT NULL REFERENCES spatial_features(id),
    to_feature_id INTEGER NOT NULL REFERENCES spatial_features(id),
    relationship_type TEXT NOT NULL,
    distance_m REAL,
    bearing_deg REAL,
    strength REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS computed_feature_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id INTEGER NOT NULL REFERENCES spatial_features(id),
    data_version_id INTEGER NOT NULL REFERENCES data_versions(id),
    metric_version TEXT NOT NULL,
    orientation_deg REAL,
    corridor_orientation_deg REAL,
    width_m REAL,
    height_m REAL,
    height_source TEXT,
    height_confidence REAL,
    hw_ratio REAL,
    curvature_score REAL,
    enclosure_ratio REAL,
    open_fetch_by_direction_json TEXT NOT NULL DEFAULT '{}',
    river_distance_m REAL,
    river_axis_deg REAL,
    vegetation_density REAL,
    slope_deg REAL,
    slope_aspect_deg REAL,
    relative_elevation_m REAL,
    nearby_highrise_score REAL,
    special_geometry_type TEXT,
    handling_mode TEXT NOT NULL DEFAULT 'normal_score',
    metric_confidence REAL NOT NULL DEFAULT 0.5,
    limitations_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(feature_id, data_version_id, metric_version)
);

CREATE TABLE IF NOT EXISTS weather_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    source TEXT NOT NULL,
    model TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timestamp TEXT NOT NULL,
    forecast_timestamp TEXT,
    is_forecast INTEGER NOT NULL DEFAULT 0,
    wind_speed_10m_ms REAL,
    wind_direction_10m_deg REAL,
    wind_gust_10m_ms REAL,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    model_type TEXT NOT NULL,
    semver TEXT NOT NULL,
    git_sha TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS scenario_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    data_version_id INTEGER NOT NULL REFERENCES data_versions(id),
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    scenario_type TEXT NOT NULL,
    reference_wind_speed_ms REAL NOT NULL,
    reference_wind_direction_deg REAL NOT NULL,
    wind_gust_ms REAL,
    weather_observation_id INTEGER REFERENCES weather_observations(id),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS scalar_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_run_id INTEGER NOT NULL REFERENCES scenario_runs(id),
    feature_id INTEGER NOT NULL REFERENCES spatial_features(id),
    risk_score REAL NOT NULL,
    exposure_class TEXT NOT NULL,
    local_multiplier REAL NOT NULL,
    approx_local_speed_ms REAL,
    gust_sensitive INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL,
    handling_mode TEXT NOT NULL,
    subscores_json TEXT NOT NULL DEFAULT '{}',
    cause_tags_json TEXT NOT NULL DEFAULT '[]',
    mitigation_tags_json TEXT NOT NULL DEFAULT '[]',
    model_note TEXT,
    limitations_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(scenario_run_id, feature_id)
);

CREATE TABLE IF NOT EXISTS directional_score_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    feature_id INTEGER NOT NULL REFERENCES spatial_features(id),
    data_version_id INTEGER NOT NULL REFERENCES data_versions(id),
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    direction_deg INTEGER NOT NULL,
    normalized_multiplier REAL NOT NULL,
    normalized_risk_score REAL NOT NULL,
    confidence REAL NOT NULL,
    subscores_json TEXT NOT NULL DEFAULT '{}',
    cause_tags_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    UNIQUE(feature_id, data_version_id, model_version_id, direction_deg)
);

CREATE TABLE IF NOT EXISTS vector_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    name TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    boundary_geom TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    reason_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'scalar_only',
    target_resolution_m REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS vector_field_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vector_zone_id INTEGER NOT NULL REFERENCES vector_zones(id),
    data_version_id INTEGER NOT NULL REFERENCES data_versions(id),
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    direction_deg REAL NOT NULL,
    reference_speed_ms REAL NOT NULL,
    height_m REAL,
    resolution_m REAL,
    field_format TEXT,
    field_path TEXT,
    bounds_geom TEXT,
    source_model TEXT,
    confidence REAL,
    created_at TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    feature_id INTEGER REFERENCES spatial_features(id),
    geom TEXT,
    feedback_type TEXT NOT NULL,
    description TEXT NOT NULL,
    wind_direction_deg REAL,
    weather_context_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    case_type TEXT NOT NULL,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    source_dataset_id INTEGER REFERENCES source_datasets(id),
    wind_direction_deg REAL,
    reference_speed_ms REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS validation_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_case_id INTEGER NOT NULL REFERENCES validation_cases(id),
    feature_id INTEGER REFERENCES spatial_features(id),
    geom TEXT,
    observed_class TEXT,
    observed_speed_ms REAL,
    predicted_class TEXT,
    predicted_score REAL,
    prediction_scenario_run_id INTEGER REFERENCES scenario_runs(id),
    confidence REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS validation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_case_id INTEGER NOT NULL REFERENCES validation_cases(id),
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id),
    data_version_id INTEGER NOT NULL REFERENCES data_versions(id),
    overall_accuracy REAL,
    high_wind_recall REAL,
    high_wind_precision REAL,
    adjacent_class_accuracy REAL,
    false_negative_rate REAL,
    metrics_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spatial_features_area ON spatial_features(area_id);
CREATE INDEX IF NOT EXISTS idx_spatial_features_type ON spatial_features(feature_type);
CREATE INDEX IF NOT EXISTS idx_scalar_results_scenario ON scalar_results(scenario_run_id);
CREATE INDEX IF NOT EXISTS idx_directional_cache_lookup ON directional_score_cache(
    area_id, data_version_id, model_version_id, direction_deg
);