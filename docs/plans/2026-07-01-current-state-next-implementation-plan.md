# Current-State Implementation Plan

Date: 2026-07-01

This plan starts from the current repo state, not the original greenfield PRD. The app already has the core v0.5 skeleton: SQLite schema, FastAPI backend, React/MapLibre frontend, OSM import, BD TOPO height enrichment, scalar scoring, gust handling, directional cache, PMTiles generation, validation harness, vector-zone metadata, and pilot UI.

The next goal is not to rebuild the product. The next goal is to make the model more evidence-driven, finish full-Lyon readiness, and add a practical pedestrian wind impact layer without drifting into CFD, black-box ML, or privacy-heavy mobility tracking.

## Current Baseline

Implemented:

- SQLite product database and migrations.
- Generic `spatial_features` schema, not street-only.
- Presqu'ile pilot import with roughly 7k features.
- `lyon_full` area and chunked pipeline command.
- BD TOPO height enrichment.
- Quay detection and promotion.
- Static feature metrics.
- Scalar scoring with sub-scores, special rules, handling modes, confidence, and gust sensitivity.
- Directional score cache.
- PMTiles generation and frontend PMTiles mode.
- Open-Meteo current/forecast integration.
- Data quality audit.
- Validation harness with manual sanity points and baselines.
- Vector-zone definitions and export endpoint.
- Frontend map, controls, explanation, validation, data quality, layers.

Known gaps:

- Full Lyon import/pipeline still needs to be run and verified end to end.
- Terrain is still weak: slope zones are seeded, but DEM-derived metrics are placeholders.
- Validation is small and pilot-local.
- Scoring weights are still hand-tuned.
- No analytics feature export exists.
- No pedestrian exposure/impact layer exists.
- Vector zones are scalar-limited; no URock/vector field generation yet.
- Public beta UX still needs an accuracy page and better feedback flow.

## Strategic Direction

Keep the product scalar-first through v0.5, but make the scalar model more measurable.

The model should evolve from:

```text
hand-written rules -> plausible exposure map
```

to:

```text
feature dataset -> rule model -> validation errors -> calibrated weights -> better exposure map
```

This does not mean jumping to ML now. It means exporting the model's inputs and outputs so we can see what the rules are doing, where they fail, and which weights need correction.

## Phase 1: Freeze and Verify Current v0.5 Baseline

Goal: establish a stable baseline before adding analytics or pedestrian impact.

Tasks:

- Run `make test`.
- Run `make validate`.
- Run `make audit AREA=pilot_presquile`.
- Run `make generate-tiles AREA=pilot_presquile DIRECTIONS=8`.
- Confirm frontend still builds through `make test`.
- Record current pilot validation metrics in `status.md`.
- Confirm no generated data files are accidentally tracked unless intentionally checked in.

Acceptance criteria:

- Backend tests pass.
- Frontend build passes.
- Pilot validation metrics are reproducible.
- Pilot tiles exist and load.
- `status.md` clearly says what is implemented, what is validated, and what remains weak.

## Phase 2: Full Lyon Pipeline Verification

Goal: prove the current pipeline can process full Lyon, not only the pilot.

Tasks:

- Run `make pipeline-lyon` in an off-peak window because Overpass may timeout.
- If Overpass fails, add retry/backoff or smaller chunks rather than manually patching data.
- Run `make audit AREA=lyon_full`.
- Generate 16-direction cache for `lyon_full`.
- Generate PMTiles for `lyon_full`.
- Verify frontend area selector can switch to full Lyon.
- Verify full Lyon map uses PMTiles instead of giant GeoJSON.
- Confirm explanation panel still works on selected full-Lyon features.

Acceptance criteria:

- `lyon_full` imports successfully.
- Full Lyon audit reports building counts, height-source tiers, special geometry counts, cached directions, and tile status.
- Full Lyon map is usable without multi-second UI stalls.
- If full import is not reliable, the failure mode and retry plan are documented.

## Phase 3: Analytics Feature Export

Goal: create the first real data-analysis artifact: one row per feature per wind direction.

This is the most important next feature for improving model precision.

Add a backend service and CLI command:

```bash
make export-analytics AREA=pilot_presquile DIRECTIONS=8
make export-analytics AREA=lyon_full DIRECTIONS=16
```

Initial output format:

- CSV first, because it is simple and easy to inspect.
- GeoJSON optional for map debugging.
- GeoParquet later when dependencies justify it.

Output columns:

- `area_slug`
- `feature_id`
- `feature_type`
- `subtype`
- `name`
- `direction_deg`
- `orientation_deg`
- `corridor_orientation_deg`
- `width_m`
- `height_m`
- `height_source`
- `height_confidence`
- `hw_ratio`
- `curvature_score`
- `enclosure_ratio`
- `river_distance_m`
- `river_axis_deg`
- `vegetation_density`
- `slope_deg`
- `slope_aspect_deg`
- `nearby_highrise_score`
- `special_geometry_type`
- `handling_mode`
- `metric_confidence`
- `normalized_multiplier`
- `normalized_risk_score`
- `exposure_class`
- `confidence`
- `subscores_json`
- `cause_tags_json`
- `validation_observed_class`
- `validation_error`

Implementation notes:

- Reuse `computed_feature_metrics` and `directional_score_cache`.
- Join validation samples where available.
- Do not add DuckDB or pandas as app dependencies yet.
- Write files under `data/analytics/{area_slug}/`.

Acceptance criteria:

- Pilot analytics CSV exports deterministically.
- Full Lyon analytics export works after pipeline.
- A developer can open the CSV and sort by risk, feature type, direction, or error.

## Phase 4: Analytics Report CLI

Goal: turn the exported feature table into actionable model diagnostics.

Add:

```bash
make analytics-report AREA=pilot_presquile
```

Report sections:

- Top 20 highest-risk features by direction.
- Average risk by feature type.
- Average risk by handling mode.
- Distribution of confidence.
- Most common cause tags.
- Features with high risk and low confidence.
- Validation errors by feature type.
- Validation errors by cause tag.
- Baseline comparison summary from existing validation metrics.

Output:

- Markdown report under `data/analytics/{area_slug}/report.md`.
- JSON summary under `data/analytics/{area_slug}/report.json`.

Acceptance criteria:

- Report identifies whether quays, bridges, high-rise clusters, and irregular zones are being over- or under-scored.
- Report makes scoring problems visible without reading code.

## Phase 5: Calibration Without ML

Goal: improve scoring weights from validation evidence while keeping the model explainable.

Do not jump to XGBoost/LightGBM yet. The sample size is too small, and a black-box model would mostly learn the current rules back from their own outputs.

Start with manual/statistical calibration:

- Add a calibration config file under `backend/src/wind_track/services/scoring/`.
- Keep the existing default scalar config as baseline.
- Add alternative model versions for tuned configs.
- Add a CLI command:

```bash
make calibrate AREA=pilot_presquile
```

First calibration logic:

- Compare observed vs predicted classes.
- Identify systematic errors.
- Suggest multiplier changes, but do not auto-promote them.
- Example: if bridge samples are under-predicted, suggest increasing bridge special multiplier.
- Example: if quays are too often high when labels say medium, suggest reducing river/quay boost.

Later calibration logic:

- Use simple grid search over selected multipliers.
- Optimize for high-wind recall first, adjacent-class accuracy second, exact accuracy third.
- Store candidate configs as new `model_versions`.

Acceptance criteria:

- Calibration command produces a clear before/after comparison.
- New tuned config can be run as a model version.
- Existing explanations still work because scoring remains subscore-based.

## Phase 6: Expand Validation Labels

Goal: make calibration meaningful.

Current 15 pilot points are enough for smoke testing, not for serious tuning.

Tasks:

- Expand Presqu'ile validation from 15 to 30-50 points.
- Add points for:
  - bridges
  - quays
  - large squares
  - sheltered side streets
  - irregular old streets
  - open exits from dense streets
- Add a second validation case for Part-Dieu / Confluence if data exists.
- Store label confidence for each sample.
- Add notes that distinguish local knowledge, field observation, benchmark, or synthetic expectation.

Acceptance criteria:

- At least 50 total validation samples.
- Validation report can be grouped by geometry type.
- Calibration does not rely on one or two bridge/quay examples.

## Phase 7: Terrain Metrics

Goal: make Lyon hills credible.

Current slope zones are useful markers, but not enough for scoring Fourviere, Croix-Rousse, valley corridors, and hill/quay transitions.

Tasks:

- Choose a DEM source for Lyon.
- Add DEM import command.
- Compute:
  - elevation
  - slope
  - aspect
  - relative elevation
  - ridge/valley marker where feasible
- Store results in `computed_feature_metrics`.
- Wire terrain subscore to real DEM-derived values.
- Add cause tags:
  - `exposed_slope`
  - `lee_shelter`
  - `valley_channeling`
  - `ridge_exposure`

Acceptance criteria:

- Fourviere and Croix-Rousse no longer use placeholder terrain.
- Terrain-heavy areas produce different scores by wind direction.
- Low confidence is shown where terrain/building interaction is too complex.

## Phase 8: Pedestrian Wind Impact Layer

Goal: answer the planning question: where does wind matter most because people are exposed?

Do not try to fully model pedestrian movement first. Build a practical priority layer.

New concept:

```text
impact_score = wind_exposure_score * pedestrian_activity_score * place_vulnerability_score
```

### Data Sources

Start with open and low-risk sources:

- Lyon mobility/pedestrian counters if available.
- OSM POIs:
  - transit stops
  - shops
  - restaurants
  - schools
  - offices
  - tourist sites
  - parks
  - public squares
- Street type and walkability tags.
- Known bridges/quays/squares from existing features.

Avoid for now:

- mobile-location providers
- Wi-Fi/Bluetooth tracking
- camera/sensor tracking
- exact individual movement models

### Schema Additions

Add `pedestrian_activity_metrics`:

- `id`
- `feature_id`
- `data_version_id`
- `metric_version`
- `time_bucket`
- `counter_count_observed`
- `counter_distance_m`
- `transit_access_score`
- `poi_density_score`
- `tourism_score`
- `school_office_score`
- `park_quay_score`
- `street_centrality_score`
- `slope_penalty`
- `pedestrian_activity_score`
- `pedestrian_activity_class`
- `confidence`
- `drivers_json`

Add `wind_impact_results`:

- `id`
- `scenario_run_id`
- `feature_id`
- `time_bucket`
- `wind_risk_score`
- `pedestrian_activity_score`
- `place_vulnerability_score`
- `impact_score`
- `impact_class`
- `confidence`
- `drivers_json`

### First Model

Use rule-based pedestrian potential:

- high near transit
- high near shops/restaurants
- high near tourist sites
- high on bridges/quays/squares
- lower on car-dominated roads
- lower on steep slopes unless known tourist/commercial route
- confidence higher near real counters

Initial classes:

- `low`
- `medium`
- `high`
- `very_high`

Acceptance criteria:

- App can show wind exposure and pedestrian wind impact as separate layers.
- A windy but empty feature is not treated as high planning priority.
- A moderately windy but very busy bridge/quay can become high priority.
- Explanation panel says why: wind causes plus pedestrian drivers.

## Phase 9: Historical Wind Frequency

Goal: add a planning-oriented view, not just a live scenario view.

Use Open-Meteo historical data first.

Tasks:

- Fetch historical wind direction/speed/gust data for Lyon.
- Aggregate by wind sector:
  - 8 sectors first
  - 16 sectors later
- Compute strong-wind frequency by sector.
- Combine with directional score cache:

```text
frequent_exposure_score =
  sum(direction_risk_score * sector_frequency * strong_wind_frequency)
```

Outputs:

- usually sheltered
- occasionally exposed
- frequently exposed
- frequently exposed during strong gust sectors

Acceptance criteria:

- Product can answer: "which places are often exposed, not just exposed under today's wind?"
- Historical exposure layer uses cached directional scores, not live recomputation.

## Phase 10: Public Beta UX Completion

Goal: make the product understandable to a non-technical user.

Tasks:

- Dedicated About Accuracy page.
- Cleaner feedback UI:
  - select map location
  - attach current wind context
  - choose issue type
- Layer menu cleanup:
  - exposure
  - confidence
  - gust risk
  - special geometry
  - pedestrian impact
  - frequent exposure
- Full Lyon default after import is verified.
- Clear labels for scalar-limited/vector-preferred zones.

Acceptance criteria:

- User understands estimated exposure vs actual wind.
- User can report "this place is usually windy/sheltered".
- No page implies CFD or certified comfort analysis.

## Phase 11: Optional ML, Only After Labels

Goal: use ML only when it has real signal.

Do not start here.

Minimum before ML:

- 100+ validation labels across multiple geometry types, or
- diagnostic/vector/benchmark reference outputs, or
- real field measurements/counterpart observations.

First ML candidates:

- logistic regression for high/medium/low classification
- ordinal regression if available
- random forest for feature importance experiments

Avoid initially:

- XGBoost/LightGBM as product model
- SHAP-heavy UI explanations
- surrogate vector-field models

Acceptance criteria before product use:

- ML model beats rule model on held-out validation data.
- High-wind recall improves without too many false positives.
- Explanations remain understandable.

## Recommended Build Order

1. Verify current baseline with tests, validation, audit, and pilot tiles.
2. Run and verify full Lyon pipeline.
3. Add analytics feature export.
4. Add analytics report CLI.
5. Expand validation labels.
6. Add calibration suggestions/grid search.
7. Add real DEM terrain metrics.
8. Add pedestrian wind impact schema, scoring, API, and layer.
9. Add historical wind frequency layer.
10. Finish public beta UX.
11. Consider ML only after stronger labels exist.

## Definition of Done for the Next Version

The next version is done when:

- Full Lyon pipeline runs reproducibly.
- Full Lyon PMTiles load in the frontend.
- Analytics export exists for pilot and full Lyon.
- Analytics report shows model behavior by direction, feature type, cause tag, and validation error.
- Validation has at least 50 labeled samples.
- Calibration can compare baseline vs candidate scoring config.
- Terrain uses real DEM-derived slope/aspect values.
- Pedestrian wind impact layer exists as a separate planning-priority layer.
- Historical wind frequency layer exists or has a working CLI prototype.
- Public beta UX explains limits clearly and supports feedback.

## Non-Goals

- Do not replace SQLite with PostGIS right now.
- Do not add Apache Sedona.
- Do not add commercial/mobile footfall data.
- Do not install public-space sensors.
- Do not claim exact pedestrian counts.
- Do not claim CFD or certified wind-comfort accuracy.
- Do not move to black-box ML before labels exist.
