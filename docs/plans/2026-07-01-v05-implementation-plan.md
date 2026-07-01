# v0.5 Implementation Plan: Full Lyon Wind Exposure Beta

## Goal

Build a full-Lyon urban wind exposure beta that stays honest about model limits, uses SQLite as the primary product database, and delivers precise, explainable scalar scoring without attempting CFD or full physics simulation.

By v0.5, users should be able to explore Lyon, select manual/current/forecast wind, see scalar exposure classes across streets and special urban zones, inspect confidence and explanations, and view selected vector-field-ready zones where advanced diagnostic modeling can be added later.

The core product claim remains:

> Street-level wind exposure estimated from regional forecast wind and urban geometry.

The product must not claim engineering-grade wind speed, certified pedestrian comfort, real-time CFD, or exact turbulent airflow.

## Product Scope Through v0.5

### Included

- Full Lyon / Metropole de Lyon coverage for scalar wind exposure.
- Manual wind scenario mode.
- Open-Meteo current and forecast wind mode.
- Streets, bridges, quays, open spaces, parks, slopes, tunnels, underpasses, high-rise clusters, and irregular old-street zones.
- Precise scoring logic with sub-scores, cause tags, confidence, and model notes.
- Precomputed scalar scoring for 8 or 16 wind directions.
- Selected vector-field-ready zones, especially Part-Dieu, Confluence, Presqu'ile river edges, major bridges, and hill/quay transition areas.
- Data quality dashboard.
- Feedback/report issue flow.
- Reproducible model and data versioning.

### Excluded

- Full CFD.
- Engineering certification.
- Exact local wind speed guarantee.
- Whole-city vector fields.
- Animation before credible vector fields exist.
- Tunnel interior airflow modeling.
- Automatic acceptance of user feedback as truth.

## Architecture Summary

Use a GIS-first architecture with SQLite at the center.

```text
source data
  -> raw import tables/files
  -> normalized spatial feature tables
  -> computed static metrics
  -> directional scalar precomputation
  -> scenario results
  -> vector tiles / GeoJSON / API responses
  -> frontend map
```

SQLite is the product database. Python does the heavy geospatial processing. Map rendering uses generated GeoJSON or PMTiles/vector tiles, not large live SQL responses for every view.

## Recommended Stack

### Frontend

- Next.js or Vite React.
- MapLibre GL JS.
- deck.gl only where it clearly improves map overlays.
- TanStack Query or equivalent for API state.
- Lightweight component system; avoid building a marketing site first.

### Backend

- Python FastAPI.
- Pydantic for request/response contracts.
- SQLAlchemy or direct SQLite access with clear repository modules.
- APScheduler, RQ, or simple worker process for ingestion/precompute jobs.

### Geospatial Processing

- GeoPandas.
- Shapely.
- PyProj.
- Fiona/pyogrio.
- Rasterio for DEM later.
- OSMnx or pyrosm for OSM import.

### Database

- SQLite.
- GeoPackage-compatible geometry storage where practical.
- RTree indexes for spatial search.
- JSON columns for source payloads, cause tags, and debug metadata.
- Explicit `model_version` and `data_version` fields on all derived outputs.

### Tile/Layer Output

- GeoJSON for early/small layers.
- PMTiles or vector tiles for full-Lyon production layers.
- Large vector/raster fields stored as files with metadata in SQLite.

## SQLite Design Principles

SQLite should be treated as a durable, versioned geospatial store, not a temporary cache.

Key rules:

- Do not make `streets` the center of the schema.
- Use generic spatial features with typed feature classes.
- Keep source identity and provenance.
- Store geometry once, then store derived metrics/results separately.
- Version every derived result by data version and model version.
- Allow multiple geometries and resolutions: street segments, polygons, points, and grid cells.
- Keep scoring outputs reproducible.
- Keep future migration to PostGIS possible by avoiding SQLite-only business logic where possible.

## Data Model

### Core Metadata

#### `areas`

Represents analysis areas.

Important fields:

- `id`
- `slug`
- `name`
- `area_type`: `pilot_zone`, `district`, `city`, `vector_zone`
- `parent_area_id`
- `boundary_geom`
- `center_lat`
- `center_lon`
- `default_zoom`
- `active`

Examples:

- `lyon_full`
- `presquile`
- `part_dieu_vector_zone`
- `confluence_vector_zone`

#### `source_datasets`

Tracks original sources.

Important fields:

- `id`
- `name`
- `provider`
- `source_type`: `bd_topo`, `bdnb`, `grand_lyon_3d`, `osm`, `dem`, `open_meteo`, `manual`
- `license`
- `attribution`
- `source_url`
- `downloaded_at`
- `raw_path`
- `version_label`
- `notes`

#### `data_versions`

Represents a complete input dataset snapshot used for calculation.

Important fields:

- `id`
- `slug`
- `created_at`
- `area_id`
- `source_dataset_ids`
- `pipeline_version`
- `status`
- `summary_json`

### Normalized Spatial Features

#### `spatial_features`

The central table. Every modeled object is a feature.

Important fields:

- `id`
- `area_id`
- `source_dataset_id`
- `source_object_id`
- `feature_type`
- `subtype`
- `name`
- `geom`
- `centroid_geom`
- `properties_json`
- `source_confidence`
- `created_at`
- `updated_at`

Feature types:

- `building`
- `street_segment`
- `bridge`
- `river`
- `quay`
- `open_space`
- `park`
- `vegetation`
- `tree_row`
- `slope_zone`
- `ridge_zone`
- `tunnel`
- `underpass`
- `arcade`
- `covered_passage`
- `high_rise_cluster`
- `irregular_fabric_zone`
- `open_exit_transition`
- `grid_cell`
- `vector_zone`

This prevents the product from becoming street-only.

#### `feature_relationships`

Stores spatial/topological relationships computed during preprocessing.

Important fields:

- `id`
- `from_feature_id`
- `to_feature_id`
- `relationship_type`
- `distance_m`
- `bearing_deg`
- `strength`
- `metadata_json`

Relationship examples:

- street adjacent to river
- street crosses river
- street exits to square
- bridge over river
- building borders street
- high-rise influences street
- open space adjacent to quay
- feature inside irregular fabric zone

### Static Metrics

#### `computed_feature_metrics`

Stores geometry-derived metrics independent of a wind scenario.

Important fields:

- `id`
- `feature_id`
- `data_version_id`
- `metric_version`
- `orientation_deg`
- `corridor_orientation_deg`
- `width_m`
- `height_m`
- `height_source`
- `height_confidence`
- `hw_ratio`
- `curvature_score`
- `enclosure_ratio`
- `open_fetch_by_direction_json`
- `river_distance_m`
- `river_axis_deg`
- `vegetation_density`
- `slope_deg`
- `slope_aspect_deg`
- `relative_elevation_m`
- `nearby_highrise_score`
- `special_geometry_type`
- `handling_mode`
- `metric_confidence`
- `limitations_json`

`open_fetch_by_direction_json` should hold directional fetch estimates for 8 or 16 directions.

### Weather

#### `weather_observations`

Stores current and forecast reference wind.

Important fields:

- `id`
- `area_id`
- `source`
- `model`
- `latitude`
- `longitude`
- `timestamp`
- `forecast_timestamp`
- `is_forecast`
- `wind_speed_10m_ms`
- `wind_direction_10m_deg`
- `wind_gust_10m_ms`
- `raw_payload_json`
- `created_at`

Open-Meteo wind is a reference input, not street-level truth.

### Model Versions

#### `model_versions`

Important fields:

- `id`
- `slug`
- `model_type`: `scalar`, `vector`, `validation`
- `semver`
- `git_sha`
- `config_json`
- `created_at`
- `notes`

The scalar model configuration must include all multiplier tables and thresholds.

### Scenario Runs

#### `scenario_runs`

Represents a user or system wind scenario.

Important fields:

- `id`
- `area_id`
- `data_version_id`
- `model_version_id`
- `scenario_type`: `manual`, `current_weather`, `forecast`
- `reference_wind_speed_ms`
- `reference_wind_direction_deg`
- `wind_gust_ms`
- `weather_observation_id`
- `status`
- `created_at`
- `completed_at`
- `summary_json`

### Scalar Results

#### `scalar_results`

Stores feature-level scoring results.

Important fields:

- `id`
- `scenario_run_id`
- `feature_id`
- `risk_score`
- `exposure_class`: `low`, `medium`, `high`, `very_high`
- `local_multiplier`
- `approx_local_speed_ms`
- `gust_sensitive`
- `confidence`
- `handling_mode`
- `subscores_json`
- `cause_tags_json`
- `mitigation_tags_json`
- `model_note`
- `limitations_json`

### Precomputed Directional Scores

#### `directional_score_cache`

Stores normalized scores for fixed directions.

Important fields:

- `id`
- `area_id`
- `feature_id`
- `data_version_id`
- `model_version_id`
- `direction_deg`
- `normalized_multiplier`
- `normalized_risk_score`
- `confidence`
- `subscores_json`
- `cause_tags_json`
- `updated_at`

Use this for v0.5 performance.

### Vector-Field-Ready Zones

#### `vector_zones`

Defines selected zones where advanced vector fields may exist.

Important fields:

- `id`
- `area_id`
- `name`
- `zone_type`: `high_rise_cluster`, `river_bridge_zone`, `hill_quay_zone`, `open_modern_district`
- `boundary_geom`
- `priority`
- `reason_json`
- `status`: `planned`, `scalar_only`, `vector_ready`, `vector_generated`
- `target_resolution_m`
- `notes`

#### `vector_field_metadata`

Stores metadata about vector fields when generated later.

Important fields:

- `id`
- `vector_zone_id`
- `data_version_id`
- `model_version_id`
- `direction_deg`
- `reference_speed_ms`
- `height_m`
- `resolution_m`
- `field_format`: `geopackage`, `zarr`, `parquet`, `raster`, `pmtiles`
- `field_path`
- `bounds_geom`
- `source_model`: `urock`, `internal_diagnostic`, `manual_import`
- `confidence`
- `created_at`
- `summary_json`

Vector fields are not required for scalar v0.5, but the schema must reserve the product boundary.

### Feedback

#### `user_feedback`

Important fields:

- `id`
- `area_id`
- `feature_id`
- `geom`
- `feedback_type`
- `description`
- `wind_direction_deg`
- `weather_context_json`
- `status`: `new`, `reviewed`, `accepted_as_hint`, `rejected`, `needs_field_check`
- `created_at`

Feedback should influence validation queues, not automatically alter truth.

### Validation

#### `validation_cases`

Important fields:

- `id`
- `name`
- `case_type`: `manual_sanity`, `field_measurement`, `benchmark`, `professional_reference`
- `area_id`
- `source_dataset_id`
- `wind_direction_deg`
- `reference_speed_ms`
- `metadata_json`

#### `validation_samples`

Important fields:

- `id`
- `validation_case_id`
- `feature_id`
- `geom`
- `observed_class`
- `observed_speed_ms`
- `predicted_class`
- `predicted_score`
- `prediction_scenario_run_id`
- `confidence`
- `notes`

#### `validation_metrics`

Important fields:

- `id`
- `validation_case_id`
- `model_version_id`
- `data_version_id`
- `overall_accuracy`
- `high_wind_recall`
- `high_wind_precision`
- `adjacent_class_accuracy`
- `false_negative_rate`
- `metrics_json`

## Scoring Model

The scalar model should be precise, decomposed, and explainable.

Output:

- `local_multiplier`
- `risk_score` from 0 to 100
- `exposure_class`
- `approx_local_speed_ms`
- `gust_sensitive`
- `confidence`
- `handling_mode`
- `cause_tags`
- `mitigation_tags`
- `model_note`

### Subscores

Each feature receives these sub-scores where applicable:

1. Directional alignment
2. Street canyon ratio
3. Downwash risk
4. Corner acceleration risk
5. Gap/passage channeling risk
6. Open exposure
7. Upwind shielding
8. River/bridge exposure
9. Vegetation reduction
10. Terrain modifier
11. Special geometry modifier
12. Gust sensitivity
13. Data confidence
14. Model suitability confidence

### Handling Modes

Every result must carry one handling mode:

- `normal_score`: standard scalar model applies.
- `special_rule`: known special geometry has a dedicated rule.
- `low_confidence`: model is likely incomplete or data is weak.
- `excluded`: do not estimate the interior condition.
- `vector_preferred`: scalar result may be shown, but UI must indicate advanced model preferred.

### Exposure Classes

Initial class mapping:

- `low`: 0-25
- `medium`: 26-50
- `high`: 51-75
- `very_high`: 76-100

These thresholds must live in `model_versions.config_json`, not hardcoded in UI.

### Score Composition

Initial structure:

```text
local_multiplier =
  M_alignment
  * M_canyon
  * M_downwash
  * M_corner
  * M_gap
  * M_open
  * M_shielding
  * M_vegetation
  * M_terrain
  * M_special_geometry
```

Then convert to `risk_score` using:

- local multiplier
- reference wind speed
- gust sensitivity
- special geometry risk
- confidence penalty only for visual confidence, not for hiding real risk

Important: low confidence should not automatically reduce risk. It should reduce certainty.

## Special Geometry Rules

### Bridges

Handling mode: `special_rule`

Inputs:

- bridge orientation
- river crossed
- river axis
- wind direction
- crosswind angle to bridge path
- nearby high-rise/slope/quay interactions

Rules:

- Apply exposed crossing multiplier.
- Increase if wind aligns with river axis.
- Add crosswind discomfort flag if wind crosses bridge path.
- Mark low confidence if complex bridge structure or nearby high-rise interactions.

Cause tags:

- `bridge_exposure`
- `open_water_fetch`
- `river_aligned_wind`
- `crosswind_discomfort`

### River Quays

Handling mode: `special_rule`

Inputs:

- river distance
- river axis
- wind alignment
- quay/open-space geometry
- embankment/building shelter
- exits from dense streets

Rules:

- Increase near-river exposure.
- Increase more for river-aligned wind.
- Add gust-transition flag at exits from dense streets to river.
- Lower confidence near underpasses, retaining walls, bridges, and complex terrain.

Cause tags:

- `river_corridor`
- `open_fetch`
- `quay_exposure`
- `gust_transition`

### Large Squares

Handling mode: `special_rule`

Inputs:

- polygon area
- enclosure ratio
- surrounding building height
- exits/gaps
- wind alignment with exits
- river/open corridor adjacency

Rules:

- Open center can be exposed.
- Enclosed center can be calmer.
- Exits and corners can be high risk.
- Large square plus high-rises becomes `vector_preferred`.

Cause tags:

- `large_open_space`
- `enclosed_square`
- `aligned_exit_gap`
- `corner_acceleration`

### Irregular Old Streets

Handling mode: `special_rule` or `low_confidence`

Inputs:

- segment length distribution
- curvature
- width variability
- enclosure
- exit proximity to river/square

Rules:

- Use corridor orientation over multiple segments.
- Reduce confidence of simple alignment.
- Dense interior often sheltered.
- Exits to river/square receive transition/gust risk.

Cause tags:

- `irregular_fabric`
- `short_curved_segments`
- `dense_enclosure`
- `open_exit_transition`

### Hills, Slopes, Ridges

Handling mode: `special_rule`

Inputs:

- DEM
- slope
- aspect
- relative elevation
- wind direction
- ridge/valley classification

Rules:

- Windward ridge/slope increases exposure.
- Lee slope reduces exposure.
- Valley aligned with wind increases exposure.
- Dense buildings plus steep terrain lowers confidence.

Cause tags:

- `exposed_slope`
- `lee_shelter`
- `ridge_exposure`
- `valley_channeling`

### Underpasses, Tunnels, Covered Passages

Handling mode: `low_confidence` or `excluded`

Rules:

- Do not estimate tunnel interior airflow.
- Tunnel entrances may receive portal/gust note.
- Underpasses are low confidence unless geometry is known.
- Covered passages and traboules are low confidence unless mapped manually.

Cause tags:

- `covered_geometry`
- `interior_flow_not_modeled`
- `portal_gust_possible`

### High-Rise Clusters

Handling mode: `vector_preferred`

Inputs:

- buildings taller than 2x surrounding median
- cluster density within 100-200 m
- corner exposure
- open-space adjacency
- gaps between towers

Rules:

- Add downwash risk.
- Add corner acceleration risk.
- Add gap/channeling risk.
- Mark scalar confidence low to medium-low.
- Add to `vector_zones` if priority is high.

Cause tags:

- `high_rise_cluster`
- `downwash_risk`
- `corner_acceleration`
- `tower_gap_channeling`
- `vector_model_preferred`

## Lyon Priority Zones

v0.5 must explicitly classify these:

1. Rhone quays
2. Saone quays
3. Major bridges and passerelles
4. Presqu'ile large squares
5. Vieux Lyon irregular street fabric
6. Fourviere slopes
7. Croix-Rousse slopes
8. Part-Dieu high-rise cluster
9. Confluence open-river and modern-building zone
10. Tunnels, underpasses, covered passages where detectable

Initial vector-field-ready zones:

- Part-Dieu
- Confluence
- Presqu'ile river-edge bridges
- Vieux Lyon / Saone / Fourviere transition
- Croix-Rousse slope/quay transition

These zones can be scalar-only initially, but the data model and UI must mark them as advanced zones.

## Implementation Milestones

### Milestone 0: Project Foundation

Deliverables:

- App scaffold.
- Backend scaffold.
- SQLite database setup.
- Migration system.
- Basic health endpoint.
- Basic map page.
- Repository docs.
- Local development commands.

Acceptance criteria:

- Frontend and backend run locally.
- SQLite file is created from migrations.
- `/health` works.
- Map loads with a base layer.

### Milestone 1: Data Schema and Seed Pipeline

Deliverables:

- SQLite schema for metadata, features, metrics, scenarios, scalar results, weather, validation, and feedback.
- Seed script with a small synthetic Lyon-like dataset.
- RTree indexes.
- Feature import contract.

Acceptance criteria:

- Can load sample buildings, streets, river, bridges, open spaces, vegetation, and special zones.
- Can query features by bbox.
- Feature types and handling modes are represented without street-only assumptions.

### Milestone 2: Real Data Research and Import Spike

Deliverables:

- Data source decision memo.
- Import prototype for OSM roads/water/open spaces/bridges.
- Import prototype for one official building-height source.
- Data audit script.

Audit metrics:

- total buildings
- buildings with official height
- buildings with fallback height
- missing-height count
- roads with width
- inferred-width count
- bridge count
- tunnel/underpass count
- river/quay detection quality
- vegetation feature count

Acceptance criteria:

- We know whether Grand Lyon, BD TOPO, or BDNB should be the first official building source.
- The audit produces a repeatable report.
- OSM is confirmed useful for roads/water/bridges/open spaces, not primary heights.

### Milestone 3: Static Feature Computation

Deliverables:

- Street orientation and corridor orientation.
- Width estimation.
- Building adjacency.
- H/W ratio.
- River distance and river-axis alignment.
- Open-space adjacency.
- Bridge detection.
- Vegetation density estimate.
- High-rise cluster detection.
- Irregular-fabric detection.
- Slope/terrain placeholders if DEM not yet imported.
- Handling mode classification.

Acceptance criteria:

- Every feature has computed metrics.
- Every feature has `handling_mode`.
- Special geometry appears separately from normal streets.
- Metrics are deterministic and versioned.

### Milestone 4: v0.1 Scalar Scenario Engine

Deliverables:

- Manual wind scenario endpoint.
- Scalar scoring model v0.1.
- Cause tags.
- Confidence calculation.
- Feature explanation endpoint.
- Map layer API for scenario result.

Acceptance criteria:

- User can select wind direction and speed.
- App colors features by exposure.
- Clicking a feature shows exposure, multiplier, confidence, cause tags, and limitations.
- Bridges/quays/squares are not scored like normal streets.

### Milestone 5: v0.1 UI

Deliverables:

- Main map.
- Wind direction control.
- Wind speed control.
- Exposure layer.
- Confidence layer.
- Special geometry layer.
- Click explanation panel.
- Conservative disclaimer.

Acceptance criteria:

- User can complete the core flow without technical knowledge.
- Low-confidence areas are visually clear.
- Explanation text matches model tags.
- No animation exists yet.

### Milestone 6: Real Pilot Data Load

Deliverables:

- Presqu'ile + river quays + bridges data load.
- Data quality dashboard for pilot zone.
- Manual validation checklist.
- 20-50 validation points.

Acceptance criteria:

- Pilot area renders quickly.
- At least 80% of visible buildings have usable official or fallback height, or gaps are explicitly reported.
- Manual sanity checks confirm bridges/quays respond plausibly to wind direction.

### Milestone 7: v0.2 Weather and Improved Scoring

Deliverables:

- Open-Meteo ingestion.
- Weather cache table.
- Current wind mode.
- Forecast hour mode.
- Time slider.
- Gust-sensitive layer.
- Expanded subscore model.

Acceptance criteria:

- Manual/current/forecast modes all work.
- Weather failures fall back to cached data.
- Gust risk is separate from steady exposure.
- Scenario results are traceable to weather source and timestamp.

### Milestone 8: Full Lyon Data Pipeline

Deliverables:

- Full Lyon area boundary.
- Full Lyon OSM import.
- Full Lyon official building import.
- DEM import if available.
- Special zone generation for Lyon priority zones.
- Data quality dashboard city-wide.

Acceptance criteria:

- Full Lyon static layers can be generated reproducibly.
- Data audit is produced for full Lyon.
- Priority special zones are detected or manually seeded.
- Known weak areas are flagged, not silently treated as normal.

### Milestone 9: Directional Precompute

Deliverables:

- 8-direction scalar precompute.
- Optional 16-direction precompute after performance check.
- Directional cache table.
- Scenario interpolation/loading logic.
- Tile generation for full Lyon scalar layers.

Acceptance criteria:

- Full Lyon cached scalar layer loads interactively.
- Switching wind direction is fast.
- Recomputing all directions is a repeatable worker job.
- Results include model/data version.

### Milestone 10: Vector-Field-Ready Zones

Deliverables:

- `vector_zones` for selected high-value areas.
- Zone priority and reason metadata.
- Export package format for diagnostic model research.
- Placeholder UI state: "advanced model preferred" or "vector field not available yet".
- Optional URock feasibility spike if time permits.

Acceptance criteria:

- Part-Dieu and other complex areas are marked as scalar-limited.
- UI does not overclaim in vector-preferred areas.
- Data exports contain buildings, terrain if available, vegetation, and wind scenario metadata.

### Milestone 11: Validation Harness

Deliverables:

- Manual sanity validation workflow.
- Validation sample tables.
- Metrics calculation.
- Baseline comparisons:
  - flat wind everywhere
  - street-alignment-only
  - building-density-only
  - full scalar model
- Validation dashboard or report output.

Acceptance criteria:

- Can run a validation case against a model version.
- Can compute confusion matrix and high-wind recall.
- Can show whether the full scalar model beats simple baselines.

### Milestone 12: v0.5 Public Beta UX

Deliverables:

- Full Lyon map.
- Scenario controls.
- Current/forecast mode.
- Layer selector.
- Explanation panel.
- Data confidence overlay.
- About accuracy page.
- Feedback/report issue button.

Acceptance criteria:

- Users can explore full Lyon.
- Rivers, bridges, hills, old districts, and high-rises are clearly represented.
- The app is useful without technical knowledge.
- Conservative trust language is visible but not intrusive.

## API Plan

### Core

- `GET /health`
- `GET /areas`
- `GET /areas/{area_id}`
- `GET /areas/{area_id}/data-quality`
- `GET /areas/{area_id}/layers`

### Features

- `GET /features?area_id=&bbox=&feature_type=`
- `GET /features/{feature_id}`
- `GET /features/{feature_id}/explanation?scenario_id=`

### Scenarios

- `POST /scenarios/scalar`
- `GET /scenarios/{scenario_id}`
- `GET /scenarios/{scenario_id}/results?bbox=`
- `GET /scenarios/{scenario_id}/tiles/{z}/{x}/{y}`

### Weather

- `GET /weather/current?area_id=`
- `GET /weather/forecast?area_id=`
- `POST /weather/refresh?area_id=`

### Validation

- `GET /validation/cases`
- `POST /validation/cases`
- `POST /validation/run`
- `GET /validation/metrics?model_version_id=`

### Feedback

- `POST /feedback`
- `GET /feedback?area_id=&status=`

## Frontend Screens

### Main Map

Primary screen. Not a landing page.

Required controls:

- Wind mode segmented control: manual, current, forecast.
- Wind direction control.
- Wind speed input.
- Forecast time slider.
- Layer menu.
- Confidence toggle.
- Special geometry toggle.
- Gust risk toggle.

Required map layers:

- Base map.
- Buildings.
- Roads/paths.
- Rivers.
- Exposure.
- Confidence.
- Special geometry.
- Vector-zone boundaries.

### Click Panel

Show:

- object type
- exposure class
- risk score
- local multiplier
- approximate local speed category
- gust sensitivity
- confidence
- main causes
- mitigating factors
- model note
- data limitations

### Data Quality View

Show:

- building count
- official height coverage
- fallback height coverage
- missing height count
- roads with inferred width
- vegetation completeness
- special geometry counts
- low-confidence area count

### About Accuracy Page

Explain:

- estimated exposure vs approximate local wind field vs validated simulation
- no CFD claim
- weather is reference wind
- confidence meaning
- known limitations

## Testing Strategy

### Unit Tests

- Bearing math.
- Wind direction angle difference.
- H/W ratio calculation.
- Multiplier tables.
- Confidence scoring.
- Handling mode classification.
- Cause tag generation.
- Weather response parsing.

### Integration Tests

- Import synthetic dataset.
- Compute static metrics.
- Run scenario.
- Store scalar results.
- Fetch map result.
- Fetch explanation.

### Golden Scenario Tests

Use a small fixed synthetic district:

- aligned street canyon
- perpendicular street canyon
- bridge over river
- quay
- large square
- high-rise cluster
- tunnel
- irregular street zone

Each scenario should assert:

- expected exposure class
- expected handling mode
- expected cause tags
- expected confidence range

### Performance Tests

- Pilot scenario under 3 seconds if not cached.
- Cached scenario under 1 second.
- Full Lyon tile/layer load under 5 seconds.
- Directional cache generation time tracked.

### Validation Tests

- Manual validation report.
- Baseline comparison.
- High-wind recall.
- Adjacent-class accuracy.

## Research Spikes Required

### Data Source Spike

Questions:

- Which official building source should be primary for Lyon?
- What is the exact height coverage?
- What license/attribution is required?
- What format is easiest to automate?

Candidates:

- Grand Lyon 3D buildings.
- IGN BD TOPO.
- BDNB.
- OSM fallback.

Output:

- Decision memo.
- Import prototype.
- Data audit.

### DEM/Terrain Spike

Questions:

- Which DEM source is practical for Lyon?
- What resolution is enough for Fourviere/Croix-Rousse?
- Can slope/aspect/ridge/valley metrics be generated reliably?

Output:

- DEM import prototype.
- Terrain metric layer.

### URock/Vector Spike

Questions:

- Can URock run headlessly?
- Can it be containerized?
- What input format does it require?
- What output format does it produce?
- Is runtime acceptable for selected zones?
- Can outputs be converted to vector/raster fields for MapLibre/deck.gl?

Output:

- Feasibility memo.
- One selected-zone test if practical.
- Decision: use URock, use as benchmark only, or defer.

### Benchmark Validation Spike

Questions:

- Which benchmark datasets are accessible?
- What geometry/result formats exist?
- Which can be loaded into our validation schema?
- Which metrics can we compute first?

Output:

- Benchmark shortlist.
- One loaded validation case if practical.

## Operational Workflow

### Local Development

Expected commands:

```bash
make dev
make test
make db-migrate
make seed
make import-osm AREA=lyon_full
make compute-metrics AREA=lyon_full
make precompute-directions AREA=lyon_full DIRECTIONS=16
make generate-tiles AREA=lyon_full
```

### Data Refresh

1. Download sources.
2. Register `source_datasets`.
3. Import raw data.
4. Normalize spatial features.
5. Create `data_versions`.
6. Compute static metrics.
7. Run directional precompute.
8. Generate tiles.
9. Run validation smoke checks.
10. Publish layer metadata.

### Model Update

1. Create new `model_versions` row.
2. Run golden scenario tests.
3. Run pilot validation.
4. Compare against previous model.
5. Generate changelog.
6. Promote model version.

## Main Risks and Mitigations

### Risk: SQLite Becomes Too Slow

Mitigation:

- Use SQLite for normalized product data and metadata.
- Use generated vector tiles/PMTiles for map serving.
- Use Python batch jobs for heavy geometry operations.
- Keep migration path to PostGIS clean.

### Risk: Scoring Looks Precise But Is Not Validated

Mitigation:

- Always show confidence.
- Store cause tags and limitations.
- Run baseline comparisons.
- Avoid exact-speed claims.

### Risk: Special Geometry Breaks Scalar Model

Mitigation:

- Use handling modes.
- Mark vector-preferred zones.
- Avoid normal scoring for tunnels/underpasses/high-rise clusters.

### Risk: Building Height Coverage Is Worse Than Expected

Mitigation:

- Audit before committing to full city.
- Store height source and confidence.
- Use fallback hierarchy.
- Lower confidence where height is weak.

### Risk: Vector Fields Become A Distraction

Mitigation:

- Keep v0.5 scalar-first.
- Store vector-zone metadata only until a credible engine is proven.
- Do not add particle animation without computed vectors.

## Definition of Done for v0.5

Product:

- Full Lyon is explorable.
- Manual/current/forecast wind modes work.
- Exposure, confidence, gust-sensitive, and special geometry layers work.
- Click explanations are useful and honest.
- Feedback can be submitted.
- Accuracy limitations are clear.

Technical:

- SQLite schema supports full Lyon and selected vector-field-ready zones.
- Data pipeline is repeatable.
- Scoring is model-versioned and reproducible.
- Directional precompute works for 8 or 16 directions.
- Map performance is acceptable.
- Weather ingestion is cached and resilient.

Model:

- Scoring logic is decomposed into precise sub-scores.
- Every result has cause tags, confidence, and handling mode.
- Special Lyon geometries are handled explicitly.
- High-rise and tunnel-like cases do not overclaim.

Validation:

- Manual Lyon validation is underway.
- Baseline comparison exists.
- At least one formal benchmark path is identified or partially loaded.
- Public claim remains conservative.

## Recommended Build Order

1. Scaffold app/backend/database.
2. Implement SQLite schema.
3. Seed synthetic geospatial sample.
4. Build scalar scoring engine against sample data.
5. Build map UI and explanations.
6. Add pilot real data import.
7. Run data audit.
8. Add Open-Meteo.
9. Expand to full Lyon data.
10. Add directional precompute and tiles.
11. Add special Lyon zones and vector-zone metadata.
12. Add validation harness.
13. Polish public beta UX.

This order protects the long-term v0.5 design while still producing a useful v0.1 quickly.
