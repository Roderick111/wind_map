PRODUCT REQUIREMENT DOCUMENT

Product name, working title:
Urban Wind Exposure Map

Product category:
GIS-based urban wind exposure and pedestrian comfort screening tool.

Core product idea:
A map application that estimates where wind is likely to be stronger, weaker, channelled, sheltered, turbulent, or uncomfortable at street level. The app combines regional wind input, city geometry, building heights, roads, rivers, bridges, trees, terrain, and special urban geometries to produce an explainable wind-exposure layer.

Important positioning:
This is not certified CFD at the beginning. The product should be positioned as an early-stage urban wind screening and visualization tool.

Correct claim:
“Street-level wind exposure estimated from regional forecast wind and urban geometry.”

Incorrect claim:
“Accurate real-time CFD simulation of wind on every street.”

The product should always distinguish between:

1. estimated exposure,
2. approximate local wind field,
3. validated engineering-grade simulation.

Reference basis:
Open-Meteo can provide wind speed and direction at 10 m through a simple API with no API key for many use cases. It exposes variables such as wind_speed_10m and wind_direction_10m. ([Open Meteo][1])

URock is an open-source diagnostic urban wind model based on the Röckle method and designed for wind-field calculation in complex urban settings. This is highly relevant for our future vector-field phase. ([GMD][2])

For France, BD TOPO is a 3D vector description of the territory and includes building-related height data; BDNB provides building-level data including morphology, surfaces, heights, and 2.5D volumes. ([INSPIRE Geoportal][3])

MapLibre GL JS is suitable for browser-based interactive maps, and deck.gl integrates with MapLibre for WebGL geospatial visualization. ([MapLibre][4])

============================================================

1. PRODUCT VISION
   ============================================================

We want to build a practical urban wind intelligence tool.

The first version should help users answer:

“Given this wind direction and strength, which streets, bridges, quays, squares, and open areas are likely to feel windy or sheltered?”

Later versions should answer:

“How does airflow move through this district?”
“What are the likely problematic pedestrian wind zones?”
“How does this site compare under different wind directions?”
“Where should planners, architects, or municipalities investigate further with CFD or field measurements?”

The product should be useful before a full professional wind study.

Primary value:
Fast identification of likely wind-exposed and sheltered zones.

Secondary value:
Interactive explanation of why places are windy or calm.

Future value:
Scenario comparison, airflow visualization, validation reports, early-stage planning support, climate adaptation analysis.

============================================================
2. TARGET USERS
===============

Primary early users:

1. Urban designers
   They need quick insight into how streets, squares, rivers, bridges, and building forms affect comfort.

2. Architects
   They need early warning before commissioning expensive CFD.

3. Real estate developers
   They need to identify wind-comfort risks around new projects.

4. Municipal teams
   They need preliminary wind-risk screening for public spaces, cycling routes, bridges, quays, and redevelopment zones.

5. Climate adaptation consultants
   They need combined analysis of urban comfort, heat, ventilation, and exposure.

Secondary users:

6. Cyclists and pedestrians
   They may want to know which routes are likely to be windy, especially near rivers, bridges, and exposed plazas.

7. Researchers / students
   They may use the tool for exploratory urban morphology and microclimate studies.

============================================================
3. CORE PRODUCT PRINCIPLES
==========================

Principle 1:
Do not overclaim.

The product must be explicit that early versions estimate wind exposure, not exact physical wind.

Principle 2:
Explain every score.

A user should be able to click a street or zone and see why it is classified as high, medium, or low wind exposure.

Principle 3:
Confidence is part of the product.

Every result should carry a confidence score based on data completeness, geometry complexity, and model suitability.

Principle 4:
Special geometries must be handled explicitly.

Bridges, river quays, hills, underpasses, tunnels, arcades, large squares, medieval streets, and high-rise clusters must not be forced blindly into a normal street formula.

Principle 5:
Animation is visualization, not truth.

Animated airflow should only appear after we generate a credible local vector field. Particles should follow computed vectors, not arbitrary decoration.

Principle 6:
Validation must use classification, not exact speed.

The realistic early target is to classify high / medium / low exposure zones correctly, not to predict exact wind speed at every point.

Principle 7:
Use open or simple data wherever possible.

For France and Lyon:

* BD TOPO / IGN for building footprints and heights.
* BDNB for enrichment.
* Grand Lyon data where available.
* OpenStreetMap for roads, paths, trees, land use, water, bridges.
* Open-Meteo for wind speed/direction.
* Optional LiDAR later for validation or high-quality zones.

============================================================
4. SCOPE SUMMARY
================

In scope:

* Map-based urban wind exposure tool.
* Scenario-based wind direction and strength.
* Optional weather-driven hourly/daily updates.
* Building, street, river, bridge, vegetation, terrain, and special-geometry analysis.
* Street-level and grid-level exposure scoring.
* Confidence and explanation layer.
* Later animated airflow visualization using vector fields.
* Validation against benchmark datasets, field checks, and professional references.

Out of scope for early MVP:

* Certified CFD.
* Real-time turbulent simulation.
* Exact pedestrian wind speed guarantee.
* Legal/planning-compliance certification.
* Full tunnel internal airflow.
* Full thermal comfort / heat stress model.
* Traffic-driven tunnel air movement.
* Guaranteed vegetation porosity modeling.
* Exact wind inside private courtyards or covered traboules unless data is known.

============================================================
5. PRODUCT PHASING
==================

============================================================
PHASE v0.1 — MVP: Lyon district wind exposure estimator
=======================================================

Goal:
Build the smallest credible product that proves the core value: estimating likely high / medium / low wind exposure on a map for one Lyon district.

Recommended first area:
Start with one district where special geometry matters but scope is manageable.

Good candidates:

* Presqu’île + Rhône/Saône quays.
* Part-Dieu.
* Vieux Lyon + Saône edge.
* Confluence.

Best first choice:
Presqu’île + nearby river quays and bridges.

Reason:
It includes normal streets, open squares, rivers, bridges, and dense old urban fabric, but is not as technically difficult as a high-rise cluster.

v0.1 core user flow:

1. User opens map.
2. User selects test area.
3. User selects wind direction manually.
4. User selects wind speed manually.
5. App colors streets and key open spaces by estimated wind exposure:

   * low,
   * medium,
   * high,
   * very high.
6. User clicks a street/zone.
7. App explains why the zone is windy or sheltered.
8. App shows confidence level.

v0.1 must not include:

* animated particles,
* full vector field,
* full CFD,
* automatic city-wide coverage,
* professional report generation,
* exact m/s guarantee.

v0.1 key features:

A. Manual wind scenario input

Inputs:

* Wind direction: N, NE, E, SE, S, SW, W, NW, or degree slider.
* Wind speed: m/s, km/h, or Beaufort-style preset.
* Default height: regional 10 m wind, interpreted as external reference wind.

Output:

* Local exposure index.
* Approximate local speed category.
* Confidence.

B. Static exposure map

Map should show:

* streets colored by exposure,
* bridges highlighted separately,
* quays highlighted separately,
* open squares highlighted separately,
* low-confidence areas visually faded or hatched.

C. Street-level scoring

For each street segment:

* calculate street orientation,
* estimate street width,
* estimate surrounding building height,
* calculate H/W canyon ratio,
* check alignment with wind,
* check upwind shielding,
* check nearby open space,
* check nearby river/water,
* check bridge condition,
* check tree/vegetation presence,
* check if geometry is special or low-confidence.

D. Basic special geometry handling

v0.1 must include at least these special rules:

1. Bridges

* Do not treat as normal roads.
* Apply exposed crossing rule.
* Increase exposure if wind aligns with river corridor.
* Add crosswind discomfort flag for cyclists/pedestrians.

2. River quays

* Treat as open-fetch corridors.
* Increase exposure near river edge.
* Increase further if wind direction aligns with river axis.

3. Large squares

* Treat separately from streets.
* Score based on open area, enclosure, exits/gaps, and wind direction.

4. Irregular old streets

* Reduce confidence of simple street-alignment score.
* Use local corridor orientation instead of single segment angle where possible.

5. Tunnels/underpasses/covered passages

* Mark low-confidence by default.
* Do not pretend to estimate internal airflow.

E. Click explanation panel

For every selected object, show:

Example:
“Exposure: High”
“Confidence: Medium”
“Estimated local class: uncomfortable under this scenario”
“Main causes:

* street aligned with southwest wind,
* open river fetch nearby,
* low tree cover,
* exposed bridge crossing.”

For sheltered area:
“Exposure: Low”
“Confidence: Medium”
“Main causes:

* large upwind building block,
* street perpendicular to wind,
* dense urban enclosure.”

F. Confidence score

v0.1 confidence should be based on:

* building height available or estimated,
* road width known or estimated,
* geometry type normal/special,
* vegetation data available,
* terrain ignored or included,
* area is open/covered/hidden,
* whether model is appropriate for the geometry.

Suggested confidence categories:

* High: good geometry, good building heights, normal street/open area.
* Medium: partial missing data or moderate special geometry.
* Low: tunnels, underpasses, arcades, complex high-rise clusters, hidden passages, poor height data.

G. Data pipeline for v0.1

Sources:

* Building footprints and heights: preferably IGN BD TOPO / Grand Lyon / BDNB.
* Roads, paths, bridges, rivers, parks, trees: OSM.
* Terrain: optional in v0.1, but store architecture for later.
* Wind: manual input only.

Processing:

* Import data into PostGIS.
* Normalize coordinate system.
* Clean building polygons.
* Attach building heights.
* Build street graph.
* Detect bridges and river-adjacent streets.
* Detect large open areas.
* Detect candidate tunnels/underpasses if possible.
* Precompute static geometry features.

H. v0.1 technical architecture

Frontend:

* Next.js or React.
* MapLibre GL JS for map.
* deck.gl optional for overlays.
* Controls for wind direction and speed.
* Side panel for explanation.

Backend:

* Python FastAPI.
* GeoPandas/Shapely for geospatial preprocessing.
* PostGIS database.
* Simple scoring endpoint.

Database:

* buildings
* roads
* street_segments
* open_spaces
* rivers
* bridges
* vegetation
* terrain_later
* computed_features
* scenario_results

API endpoints:

* GET /areas
* GET /map/base-layers
* POST /wind-scenario
* GET /street/:id/explanation
* GET /data-quality/:area_id

v0.1 success criteria:

Product:

* User can select wind direction/speed and see meaningful high/medium/low street exposure.
* User can understand why a street is classified that way.
* Special areas do not look falsely precise.

Technical:

* Process one district in Lyon.
* Response time for scenario calculation under 3 seconds if precomputed features exist.
* Map layer loads under 5 seconds for selected district.
* At least 80% of visible buildings have usable height from official data or fallback.
* Low-confidence areas are visibly marked.

Validation:

* Manual sanity check on 20–50 selected points.
* Compare against local knowledge:

  * bridges should usually be more exposed,
  * quays should respond strongly to river-aligned wind,
  * sheltered side streets should be lower,
  * large squares should show internal variation or special handling.

v0.1 non-goals:

* No formal published validation claim yet.
* No animated airflow.
* No vector-field solver.
* No annual comfort statistics.
* No professional report exports.

============================================================
PHASE v0.2 — Lyon beta: weather integration, better scoring, special geometry layer
===================================================================================

Goal:
Make the product usable as a live or semi-live urban wind exposure tool for Lyon, still based on scalar exposure scoring, but with better data and automatic wind input.

New capabilities:

A. Open-Meteo weather integration

Use Open-Meteo to fetch:

* wind_speed_10m,
* wind_direction_10m,
* wind_gusts_10m,
* hourly forecast.

Open-Meteo is suitable because it exposes hourly wind variables in a simple API and does not require an API key for many use cases. ([Open Meteo][1])

Backend behavior:

* Fetch current wind every hour.
* Fetch 24–48h hourly forecast every 3 hours.
* Cache response.
* Store source, timestamp, wind speed, direction, gusts, raw payload.
* Let user switch between:

  * manual scenario,
  * current wind,
  * forecast hour.

Weather data table:
weather_observations

* id
* area_id
* latitude
* longitude
* source
* model
* timestamp
* wind_speed_10m_ms
* wind_direction_10m_deg
* wind_gust_10m_ms
* raw_payload_json
* created_at

B. Time slider

Allow user to inspect:

* now,
* +1h,
* +3h,
* +6h,
* tomorrow.

In v0.2, the map recomputes scalar exposure for each time.

C. Improved scoring model

Move from one simple formula to sub-scores:

1. Directional exposure score
2. Street canyon score
3. Building height/downwash risk score
4. Corner acceleration risk
5. Gap/passage channeling risk
6. Open-space exposure score
7. Upwind shielding score
8. River/bridge exposure score
9. Vegetation reduction score
10. Terrain modifier, if available
11. Special-geometry modifier
12. Confidence score

The final result should be:

* exposure class,
* estimated local wind multiplier,
* risk score 0–100,
* cause tags,
* confidence.

D. Gust risk layer

Use wind gusts as a separate warning, not as the main steady wind value.

Output:

* steady exposure,
* gust-sensitive zones.

High gust-sensitive zones:

* bridges,
* river quays,
* exposed corners,
* exits from sheltered streets to open spaces,
* high-rise cluster corners,
* hill ridges.

E. More special geometry detection

v0.2 should detect and classify:

1. Bridges
2. River quays
3. Large squares
4. Parks and open spaces
5. Sloped streets
6. Hill/ridge/lee-side zones, if DEM available
7. Tunnels / underpasses
8. Arcades / covered passages where data exists
9. Irregular medieval street networks
10. High-rise clusters
11. Open exits from dense fabric to river/square

Each object gets:

* geometry_type,
* handling_mode,
* confidence,
* model_note.

Example:
geometry_type = bridge
handling_mode = special_rule
main_risks = open_fetch, river_alignment, crosswind
confidence = 0.68

F. Data quality dashboard

Internal/admin view:

* number of buildings,
* percentage with official height,
* percentage with estimated height,
* roads with inferred width,
* vegetation completeness,
* special geometry count,
* low-confidence zones.

G. Fallback height model

If official building height is unavailable:

Priority:

1. exact official height,
2. roof/facade height from local 3D data,
3. BDNB height/morphology,
4. OSM height,
5. building:levels × floor height,
6. building type default,
7. neighborhood median,
8. mark low confidence.

Suggested fallback assumptions:

* one floor ≈ 3.0 m,
* house ≈ 6–8 m,
* apartment block ≈ 12–20 m,
* warehouse/industrial ≈ 6–12 m,
* unknown: neighborhood median.

Do not silently use fallback height. Store source and confidence.

H. v0.2 success criteria

Product:

* User can switch between manual, current, and forecast wind.
* Product handles Lyon rivers and bridges visibly better than normal street scoring.
* Explanations include special-geometry causes.
* Low-confidence areas are clear.

Technical:

* Hourly weather ingestion stable.
* Scenario recomputation/cached response fast enough for interactive use.
* Data quality dashboard available internally.
* Full selected Lyon area can be processed.

Validation:

* 50–100 manual test points.
* Compare v0.2 model against v0.1 model.
* Confirm special rules improve plausibility near bridges, rivers, slopes, and squares.

============================================================
PHASE v0.3 — Credible vector field and airflow visualization
============================================================

Goal:
Move from scalar street scoring to an approximate local wind vector field, then use it for animated airflow visualization.

Important rule:
Do not add animated particles until a vector field exists.

v0.3 core concept:
The vector field becomes the source of truth. Animation becomes a visualization of that field.

A. Research engine: URock

Use URock or a URock-style pipeline as the first serious vector-field engine.

URock is an open-source GIS-based diagnostic model for urban wind fields, based on Röckle-type methods and implemented in the QGIS/UMEP ecosystem. ([GMD][2])

Why URock first:

* urban-specific,
* open-source,
* based on diagnostic empirical building-flow zones,
* uses GIS inputs,
* outputs wind fields,
* more practical than full CFD,
* more credible than visual-only particles.

B. Vector field outputs

For each grid cell at pedestrian height:

* x,
* y,
* height_m,
* u wind component,
* v wind component,
* speed,
* direction_deg,
* turbulence/variability proxy,
* confidence,
* main_effect,
* source_model.

Example:
{
x: 184,
y: 92,
height_m: 1.5,
u: 3.2,
v: -1.1,
speed: 3.38,
direction_deg: 109,
turbulence: 0.4,
confidence: 0.72,
main_effect: street_canyon
}

C. Grid resolution

For v0.3:

* 5 m grid for district-scale beta.
* 2 m grid only for small pilot zones.
* Pedestrian-height output at 1.5–2 m.
* Optional additional heights: 5 m, 10 m.

D. Vector-field workflow

1. Load city geometry.
2. Build 3D/2.5D obstacles from buildings.
3. Add vegetation as porous/attenuation zones where possible.
4. Input regional wind speed and direction.
5. Initialize urban wind field with empirical zones:

   * upwind slowdown,
   * side acceleration,
   * corner acceleration,
   * rooftop recirculation,
   * downwind wake,
   * street canyon effects,
   * intersection/gap effects,
   * vegetation attenuation.
6. Apply mass-conservation correction where available.
7. Extract pedestrian-height field.
8. Store vector tiles/rasters.
9. Render static and animated layers.

E. Precomputation strategy

Precompute vector fields for:

* 8 directions in early v0.3,
* 16 directions in mature v0.3/v0.4.

Directions:

* N, NE, E, SE, S, SW, W, NW for first version.
* Later every 22.5 degrees.

Speed scaling:

* Store normalized speed-up ratios.
* Multiply by current/selected regional wind speed.

F. Frontend airflow visualization

Visual modes:

Mode 1:
Static exposure map.
This remains the main truth layer.

Mode 2:
Vector arrows.
Useful for expert/debug mode.

Mode 3:
Animated particles.
Particles follow computed u/v field.

Particle properties:

* speed = local wind speed,
* density = flow intensity,
* opacity/brightness = strength or confidence,
* jitter = turbulence/uncertainty,
* fade = low-confidence areas.

Do not use too many colors. Avoid noisy visualization.

G. Animation wording

UI label:
“Approximate mean airflow.”

Not:
“Real turbulent airflow simulation.”

Tooltip:
“Flow animation is generated from an approximate urban wind-field model and should be used for screening, not engineering certification.”

H. v0.3 success criteria

Product:

* User sees airflow movement that corresponds to map logic.
* Bridges, river corridors, street canyons, corners, and wakes look directionally plausible.
* Animation and static score agree.

Technical:

* Vector field generated for one pilot district and 8 wind directions.
* Frontend smoothly animates particles on desktop and acceptable mobile devices.
* Vector field can be cached and served as tiles or compact raster grid.
* User can toggle layers.

Validation:

* Compare vector-field high-speed zones against scalar model.
* Check whether vector field improves known problematic zones.
* No public accuracy claim yet unless benchmark validation exists.

============================================================
PHASE v0.4 — Formal validation and calibration
==============================================

Goal:
Prove the model is useful enough using benchmark datasets, local field checks, and clear metrics.

Validation claim to prove:
“Our model predicts high / medium / low wind-exposure zones correctly in X% of cases.”

Not:
“Our model predicts exact local wind speed perfectly.”

A. Benchmark datasets

Use 5–10 cases from:

* AIJ urban wind benchmark cases,
* Niigata / Shinjuku / high-rise block cases,
* Michelstadt / CEDVAL,
* MUST urban array,
* Ecole Centrale de Lyon tree-canyon dataset,
* Livorno historic district case,
* UrbanTALES LES dataset.

B. Comparison method

For each benchmark:

1. Load geometry.
2. Run our model with same wind direction.
3. Sample our result at measurement/CFD points.
4. Convert benchmark result to low/medium/high.
5. Convert our result to low/medium/high.
6. Build confusion matrix.
7. Calculate metrics.

C. Classification strategy

Use relative classification first:

* Low = bottom 30%.
* Medium = middle 50%.
* High = top 20%.

Reason:
Different datasets use different reference speeds, scales, and measurement setups. Relative classification is more robust for MVP validation.

Later:
Map to comfort standards such as Lawson / City of London / NEN-type thresholds.

City of London wind microclimate guidance uses exceedance-based comfort and safety logic, not just one instant wind speed. It references 5% exceedance for comfort and much rarer exceedance for safety. ([City of London][5])

D. Metrics

Core metrics:

* overall low/medium/high accuracy,
* high-wind recall,
* high-wind precision,
* adjacent-class accuracy,
* top-20% windy-zone overlap,
* high-zone IoU,
* false-negative rate for high-wind zones.

Priority metric:
High-wind recall.

Reason:
Missing a real high-wind zone is worse than over-warning.

Targets for v0.4:

* Overall accuracy: 70–80%.
* High-wind recall: at least 80%.
* High-wind precision: 60–70%.
* Adjacent-class accuracy: at least 90%.
* Top-20% overlap: at least 70%.
* High-wind false negatives: minimized.

E. Baseline comparison

Compare against:

1. flat wind everywhere,
2. street-alignment-only model,
3. building-density-only model,
4. our scalar model,
5. our vector-field model.

We need to prove:
full model > simple baselines.

F. Calibration process

Use strict train/test split.

Calibration set:

* tune multipliers and rules.

Test set:

* unseen geometry and unseen wind directions.

Do not tune and test on the same exact cases.

G. Local Lyon validation

Use:

* local windy-place knowledge,
* bridge/quay checks,
* handheld anemometer spot measurements,
* weather station reference wind,
* user reports,
* optional temporary sensors.

Field test structure:

* select 20–50 points,
* measure under 3–5 wind conditions,
* compare relative ranking,
* not exact speed.

H. v0.4 deliverable

Validation report should say something like:

“Across 7 benchmark cases, the model classified low / medium / high wind-exposure zones with 76% overall accuracy. It detected 83% of high-wind zones with 68% precision. In 91% of tested points, the model was either correct or only one class away. The model outperformed flat, street-only, and density-only baselines.”

This becomes the first credible commercial proof.

============================================================
PHASE v0.5 — Lyon full beta
===========================

Goal:
Expand from one pilot district to full Lyon / Métropole de Lyon coverage with robust data, weather, special geometry, scalar scoring, and selected vector-field zones.

A. Geographic coverage

Include:

* Presqu’île,
* Vieux Lyon,
* Fourvière slopes,
* Croix-Rousse slopes,
* Part-Dieu,
* Confluence,
* Rhône quays,
* Saône quays,
* major bridges,
* large squares,
* major parks,
* exposed hill/ridge zones.

B. Lyon-specific special zones

The following must be treated as special from day one:

1. Rhône and Saône quays
2. All bridges and passerelles
3. Fourvière and Croix-Rousse slopes
4. Vieux Lyon irregular medieval streets
5. Presqu’île large squares
6. Part-Dieu high-rise cluster
7. Confluence open-river / modern-building zone
8. Tunnels / underpasses / covered passages

C. City-wide performance

Precompute:

* static geometry features,
* scalar exposure factors for 8/16 directions,
* vector fields only for selected high-value zones.

Do not compute expensive vector fields live for the whole city.

D. Public beta UX

Core pages:

1. Map
2. Scenario controls
3. Current/forecast wind mode
4. Layer selector
5. Click explanation panel
6. Data confidence overlay
7. “About accuracy” page
8. Feedback/report issue button

E. Feedback loop

Allow users to submit:

* “This place is usually windy”
* “This place is sheltered”
* “Bridge feels dangerous in crosswind”
* “Tree coverage wrong”
* “Construction changed area”

Store feedback but do not automatically treat as truth.

F. v0.5 success criteria

Product:

* Users can explore full Lyon.
* Product clearly identifies rivers, bridges, hills, and high-rise zones.
* App feels useful without requiring technical knowledge.

Technical:

* City-wide static layers performant.
* Weather updates stable.
* Vector fields available for selected zones.
* Confidence and data-quality system robust.

Validation:

* Local validation campaign underway.
* At least one formal benchmark validation completed.
* Public claim remains conservative.

============================================================
PHASE v1.0 — Commercial screening product
=========================================

Goal:
Turn the tool into a product for architects, urban designers, municipalities, and developers.

A. Professional workflows

Features:

* save project areas,
* compare wind directions,
* compare current vs forecast,
* export map screenshots,
* export simple PDF/HTML reports,
* create scenario packages:

  * winter prevailing wind,
  * storm/gust condition,
  * summer ventilation,
  * pedestrian comfort risk.

B. Report output

Report should include:

* project area,
* data sources,
* model version,
* wind scenario,
* exposure map,
* high-risk zones,
* low-confidence zones,
* key drivers,
* recommended next steps,
* disclaimer.

Report wording:
“Preliminary wind exposure screening. Not a substitute for CFD, wind tunnel, or certified pedestrian wind comfort assessment.”

C. Role-based use

User types:

* viewer,
* analyst,
* admin.

D. Paid product surfaces

Possible packaging:

1. Free public map for selected city.
2. Professional project reports.
3. API access.
4. Municipality dashboard.
5. Developer/architect project workspaces.

E. v1.0 success criteria

Commercial:

* 5–10 professional pilot users.
* At least 3 use cases where product identifies issue before CFD or field check.
* Users understand limitations.
* Product produces useful reports.

Technical:

* Stable backend.
* Versioned scoring model.
* Versioned datasets.
* Reproducible calculations.
* Exportable results.

Validation:

* Published validation summary.
* High-wind recall target met or honestly documented.
* Known failure cases documented.

============================================================
PHASE v1.1 — France expansion
=============================

Goal:
Scale from Lyon to other French cities using national open data.

Target cities:

* Paris,
* Marseille,
* Lille,
* Bordeaux,
* Nantes,
* Toulouse,
* Strasbourg,
* Grenoble,
* Nice.

Data strategy:

* BD TOPO for national building geometry and height.
* BDNB for enrichment.
* OSM for roads/vegetation/water.
* local open data where available.
* Open-Meteo for wind input.
* optional city LiDAR/3D data for premium zones.

A. City onboarding pipeline

For each new city:

1. Import boundary.
2. Import buildings.
3. Attach height.
4. Import streets/bridges/water/open spaces.
5. Import terrain.
6. Detect special geometries.
7. Run data quality audit.
8. Precompute 8/16 wind directions.
9. Validate with 10–20 local sanity points.
10. Publish with confidence layer.

B. National consistency

Need:

* common model version,
* common data schema,
* city-specific configuration,
* local special rules,
* consistent UX.

C. v1.1 success criteria

* Add one new city in less than one week of data work.
* Data audit automatically generated.
* More than 80% of buildings in target city have usable official or fallback height.
* Special geometry detection works across cities.

============================================================
PHASE v2.0 — Advanced wind-field engine
=======================================

Goal:
Build or integrate a more scalable diagnostic wind-field engine and reduce dependency on external GIS workflows.

A. Own simplified diagnostic solver

Implement our own simplified version inspired by:

* Röckle-type zones,
* URock methodology,
* mass-conservation correction,
* street-canyon logic,
* building wake/corner/gap logic.

Core pipeline:

1. Rasterize buildings and vegetation.
2. Initialize regional wind.
3. Apply empirical zones.
4. Apply building boundary constraints.
5. Solve mass-conservation correction.
6. Export pedestrian-level vector field.
7. Generate exposure classes.

B. Optional QES-Winds exploration

QES-Winds is a fast-response diagnostic urban wind model with C++/CUDA requirements. It may be useful later but is heavier than a Python/GIS MVP.

Use only if:

* URock is too slow,
* we need GPU acceleration,
* we need stronger 3D handling.

C. ML surrogate model exploration

Long-term possibility:

* Train model on CFD/LES/diagnostic outputs.
* Input geometry raster + wind direction.
* Output vector field.
* Use for fast city-scale inference.

Do not start here.

ML is v2/v3, after validation and data pipeline maturity.

D. Sensor/data assimilation

Future:

* ingest local sensors,
* compare model vs observations,
* adjust uncertainty,
* calibrate district-level roughness.

E. v2.0 success criteria

* Internal solver produces vector fields comparable to URock on selected cases.
* Runtime suitable for precomputing large areas.
* Validation metrics do not degrade.
* Animation and scoring use same vector field.

============================================================
6. SCORING MODEL SPECIFICATION
==============================

The model should output two main values:

1. Estimated local wind multiplier
   This is a speed-up or reduction factor relative to reference wind.

2. Wind exposure score 0–100
   This is the user-facing classification score.

Basic formula:
local_wind_speed = reference_wind_speed × total_multiplier

Total multiplier is built from sub-factors:

* M_alignment
* M_canyon
* M_downwash
* M_corner
* M_gap
* M_open
* M_shielding
* M_vegetation
* M_terrain
* M_special_geometry

Important:
These multipliers are initial assumptions. They must be calibrated later.

A. Directional alignment

Purpose:
Detect whether wind can travel along a street corridor.

Inputs:

* wind direction,
* street bearing,
* street curvature,
* local corridor orientation.

Rules:

* street aligned with wind = higher exposure,
* perpendicular street = lower direct exposure,
* irregular/curved streets = lower confidence.

Initial multipliers:

* 0–15° difference: 1.35
* 15–30°: 1.20
* 30–60°: 1.05
* 60–75°: 0.90
* 75–90°: 0.80

B. Street canyon ratio

H/W = average building height / street width.

If street aligned with wind:

* H/W < 0.3: 1.00
* 0.3–0.75: 1.10
* 0.75–1.5: 1.20
* 1.5–2.5: 1.30
* > 2.5: 1.20, because very deep canyons may become partially decoupled.

If street perpendicular to wind:

* H/W < 0.3: 1.00
* 0.3–0.75: 0.95
* 0.75–1.5: 0.85
* 1.5–2.5: 0.75
* > 2.5: 0.70

C. Downwash risk

Purpose:
Detect tall buildings that may redirect upper-level wind to pedestrian level.

Inputs:

* building height,
* surrounding median height,
* distance from building base,
* windward façade exposure,
* podium/setback/canopy if known.

Initial multipliers:

* building < 15 m: 1.00
* 15–30 m: 1.05
* 30–60 m: 1.15
* 60–100 m: 1.25
* > 100 m: 1.35
* building >2× surrounding height: +0.10
* exposed windward façade: +0.10
* podium/setback/canopy: -0.10 to -0.25

Apply strongest within 0–1H of base, medium 1–2H, weak 2–4H.

D. Corner acceleration

Purpose:
Detect localized acceleration around exposed building corners.

Inputs:

* distance to corner,
* building height,
* corner exposure to wind,
* corner angle,
* surrounding openness.

Initial multipliers:

* no exposed corner: 1.00
* within 30 m: 1.05
* within 15 m: 1.15
* within 5 m: 1.30
* sharp tall exposed corner: +0.10
* rounded/stepped corner: -0.10 if known

E. Gap / passage channeling

Purpose:
Detect wind acceleration through gaps between buildings, passages, and underpasses.

Inputs:

* gap width,
* gap length,
* building heights on both sides,
* alignment with wind,
* whether passage is covered/open.

Initial multipliers:

* no gap: 1.00
* wide gap weakly aligned: 1.05
* medium gap aligned: 1.15
* narrow gap aligned: 1.30
* underpass/arcade: 1.20–1.50 only if geometry known; otherwise low-confidence.

Important:
Do not blindly apply “narrower = faster.” Urban passage flow is not always a simple Venturi effect.

F. Open exposure

Purpose:
Detect exposed areas such as plazas, riverbanks, bridges, and parking lots.

Inputs:

* open area size,
* distance to open area,
* upwind fetch length,
* water surface,
* enclosure ratio,
* tree cover.

Initial multipliers:

* dense surroundings: 0.85–1.00
* normal street: 1.00
* wide boulevard: 1.05
* large square: 1.15
* riverbank/waterfront: 1.20
* bridge: 1.30
* long open upwind fetch: +0.10 to +0.30

G. Upwind shielding

Purpose:
Detect shelter from buildings or dense blocks.

Inputs:

* upwind obstacle height,
* obstacle width,
* distance behind obstacle,
* wake cone,
* continuity of block.

Initial multipliers:

* no obstacle: 1.00
* small upwind obstacle: 0.95
* large building upwind: 0.80
* continuous block upwind: 0.65
* deep wake zone: 0.50–0.75

Approximate wake:

* wake length = 5–10 × obstacle height,
* wake cone angle = 15–30° behind obstacle.

H. Vegetation

Purpose:
Represent wind reduction and turbulence from trees/hedges.

Inputs:

* tree density,
* tree height,
* crown diameter,
* hedge/tree row continuity,
* evergreen/deciduous if known,
* season,
* gaps.

Initial multipliers:

* no vegetation: 1.00
* scattered trees: 0.95
* tree row: 0.85–0.90
* dense hedge/evergreen barrier: 0.70–0.85
* aligned gaps: add +0.05 to +0.15 locally

v0.1:
Vegetation should be a minor correction, not dominant.

I. Terrain

Purpose:
Handle hills, ridges, slopes, river valleys.

Inputs:

* DEM,
* slope,
* aspect,
* relative elevation,
* ridge/valley detection,
* wind direction relative to slope/valley.

Initial multipliers:

* ridge/exposed slope: 1.10–1.30
* lee side: 0.75–0.95
* valley aligned with wind: 1.15–1.35
* flat terrain: 1.00

v0.1:
Terrain optional, but Lyon v0.2+ should include it because of Fourvière, Croix-Rousse, and river valleys.

J. Special geometry modifier

Each special geometry can override or modify normal scoring.

Special geometry types:

* bridge,
* river_quay,
* large_square,
* sloped_street,
* hill_ridge,
* valley_corridor,
* underpass,
* tunnel,
* arcade,
* covered_passage,
* medieval_irregular_fabric,
* high_rise_cluster,
* open_exit_transition,
* construction_unknown.

Each must define:

* handling_mode: normal_score, special_rule, low_confidence, excluded,
* multiplier logic,
* explanation tags,
* confidence impact.

============================================================
7. SPECIAL GEOMETRY HANDLING
============================

A. Normal street canyon

Handling:
Score normally.

Required:

* street orientation,
* width estimate,
* building height,
* alignment,
* shielding,
* vegetation.

Confidence:
Medium to high if data is good.

B. Large square

Handling:
Special rule.

Factors:

* area,
* enclosure ratio,
* surrounding building height,
* number/width of exits,
* wind alignment with exits,
* river/open-corridor adjacency,
* corner risk.

Rule:

* open center may be exposed,
* enclosed center may be calmer,
* exits/gaps may be windy,
* corners may be locally high.

Confidence:
Medium; low if high-rise/irregular geometry.

C. Bridge

Handling:
Special rule.

Factors:

* river crossing,
* bridge orientation,
* river orientation,
* wind alignment with river,
* crosswind to bridge path,
* bridge barriers/superstructure if known.

Rule:

* bridge base exposure increased,
* river-aligned wind increases exposure,
* crosswind adds cyclist/pedestrian discomfort warning.

Confidence:
Medium for open bridges; low for complex/enclosed bridges.

D. River quay

Handling:
Special rule.

Factors:

* distance to river,
* river axis,
* wind alignment,
* embankment/wall/building shelter,
* open fetch length,
* bridge interaction.

Rule:

* near-river exposure increases,
* river-aligned wind increases more,
* exits from dense streets to quays get transition/gust flag.

Confidence:
Medium; low near underpasses, steep retaining walls, bridges, complex buildings.

E. Hill / slope / ridge

Handling:
Special terrain rule.

Factors:

* slope,
* aspect,
* elevation,
* wind direction,
* ridge/lee-side position.

Rule:

* windward ridges/slopes increase,
* lee slopes reduce,
* valleys aligned with wind increase.

Confidence:
Medium with good DEM; low if dense buildings and steep terrain interact.

F. Underpass

Handling:
Low-confidence by default.

Rule:

* do not apply normal street canyon score blindly,
* if openings align with wind, mark possible acceleration,
* if geometry unknown, show uncertain.

Confidence:
Low unless height, width, length, openings are known.

G. Tunnel

Handling:
Excluded or low-confidence.

Rule:

* tunnel interior airflow not modeled,
* tunnel entrances may get portal gust warning,
* no internal wind claim.

Confidence:
Low.

H. Arcade / covered passage / traboule

Handling:
Low-confidence unless geometry is known.

Rule:

* if open aligned passage: possible acceleration,
* if hidden/covered/interior: not modeled,
* mark manually or use local data later.

Confidence:
Low by default.

I. Irregular medieval street network

Handling:
Special morphology rule.

Factors:

* short segments,
* high curvature,
* variable width,
* high enclosure,
* hidden courtyards/passages,
* exits to open spaces/rivers.

Rule:

* reduce confidence of simple alignment score,
* compute local corridor orientation over multiple segments,
* likely sheltered inside dense fabric,
* gust-transition risk at exits.

Confidence:
Medium-low.

J. High-rise cluster

Handling:
Diagnostic vector field preferred; scalar model low-confidence.

Factors:

* buildings >2× surrounding height,
* multiple high-rises within 100–200 m,
* tower spacing,
* corner exposure,
* downwash,
* gaps between towers.

Rule:

* add downwash risk,
* add corner acceleration,
* add gap/channeling risk,
* mark low-confidence unless vector-field model is active.

Confidence:
Low with scalar only, medium with diagnostic vector field.

K. Large square + high-rises

Handling:
Advanced / low-confidence.

Rule:

* do not strong-claim with scalar model,
* use vector field if available,
* otherwise classify as “requires advanced assessment.”

L. Bridge next to high-rise / quay / slope

Handling:
Advanced / low-confidence.

Rule:

* multiple interacting effects,
* use conservative high exposure warning,
* confidence medium-low or low.

============================================================
8. DATA REQUIREMENTS
====================

A. Building data

Required:

* footprint polygon,
* height,
* source of height,
* confidence,
* building type if available,
* roof/facade height if available,
* construction/usage optional.

Preferred sources for Lyon:

1. Grand Lyon 3D building data
2. IGN BD TOPO
3. BDNB
4. OSM as fallback
5. LiDAR for validation/sample correction

BD TOPO and BDNB are particularly relevant because they provide official building morphology/height-related data for France. ([INSPIRE Geoportal][3])

Building table:
buildings

* id
* geom
* height_m
* height_source
* height_confidence
* building_type
* levels
* roof_height
* facade_height
* data_source
* updated_at

B. Street data

Required:

* road/path geometry,
* type,
* bridge flag,
* tunnel flag,
* width if known,
* inferred width,
* orientation,
* local corridor orientation,
* slope if available.

Source:

* OSM / OSMnx.

OSMnx is suitable for downloading and analyzing street networks and other OpenStreetMap features in Python. ([Python GIS][6])

Street table:
street_segments

* id
* geom
* road_type
* bridge
* tunnel
* covered
* width_m
* width_source
* bearing_deg
* corridor_bearing_deg
* slope
* confidence
* data_source

C. Water / rivers

Required:

* river geometry,
* river axis orientation,
* river width,
* quay adjacency,
* bridge crossings.

D. Open spaces

Required:

* polygon,
* type: square, park, plaza, parking, waterfront, courtyard,
* area,
* enclosure ratio,
* surrounding building height,
* exits/gaps.

E. Vegetation

Required:

* trees,
* tree rows,
* parks,
* woodland,
* hedges if available.

Optional:

* tree height,
* crown diameter,
* deciduous/evergreen,
* density,
* porosity estimate.

F. Terrain

Required v0.2+:

* DEM,
* slope,
* aspect,
* relative elevation,
* ridge/valley classification.

G. Weather

Required v0.2+:

* wind speed at 10 m,
* wind direction at 10 m,
* gusts,
* timestamp,
* source/model.

H. Validation data

Required v0.4+:

* benchmark geometries,
* measured/CFD speed fields,
* reference wind direction,
* reference speed,
* measurement height,
* metadata.

============================================================
9. SYSTEM ARCHITECTURE
======================

v0.1 architecture:

Frontend:

* Next.js / React
* MapLibre GL JS
* optional deck.gl
* controls for scenario
* layer toggles
* click explanation panel

Backend:

* Python FastAPI
* GeoPandas
* Shapely
* PyProj
* Rasterio later
* OSMnx for OSM data
* PostGIS

Database:

* PostgreSQL + PostGIS

Caching:

* Redis optional in v0.1
* required v0.2+

Workers:

* Celery/RQ optional in v0.1
* required for precomputation in v0.2+

v0.3+ additional architecture:

* wind solver service,
* vector-field tile generator,
* object storage for precomputed grids,
* WebGL animation layer.

Suggested services:

1. Data ingestion service

* downloads/imports source data,
* cleans geometry,
* deduplicates,
* joins heights.

2. Feature computation service

* computes orientation,
* H/W ratio,
* shielding,
* open fetch,
* river proximity,
* special geometry flags.

3. Scenario scoring service

* takes wind speed/direction,
* computes exposure classes,
* returns GeoJSON/vector tiles.

4. Weather service

* fetches Open-Meteo,
* caches forecasts,
* stores observations.

5. Vector-field service

* runs URock or internal solver,
* stores pedestrian-height vector fields.

6. Validation service

* runs benchmark comparisons,
* computes metrics.

7. Frontend map app

* renders map,
* exposure layers,
* airflow animation,
* explanations.

API endpoints:

GET /health
GET /areas
GET /areas/:id/data-quality
GET /areas/:id/layers
POST /scenario/scalar
POST /scenario/vector
GET /scenario/:id/result
GET /feature/:id/explanation
GET /weather/current?area_id=
GET /weather/forecast?area_id=
GET /validation/summary
POST /feedback

============================================================
10. FRONTEND REQUIREMENTS
=========================

A. Main map

Must include:

* base map,
* buildings visible,
* roads,
* rivers,
* bridges,
* exposure overlay,
* confidence overlay,
* special geometry overlay.

B. Controls

v0.1:

* wind direction selector,
* wind speed input,
* scenario run button,
* exposure layer toggle,
* confidence layer toggle.

v0.2:

* current wind toggle,
* forecast time slider,
* gust risk toggle.

v0.3:

* airflow animation toggle,
* vector arrows toggle,
* particle density control,
* animation speed control.

C. Click panel

Must show:

* object name/type if known,
* exposure class,
* score,
* estimated local multiplier,
* main causes,
* mitigating factors,
* confidence,
* data limitations,
* model note.

D. Visual language

Exposure:

* low,
* medium,
* high,
* very high.

Confidence:

* high confidence: normal opacity,
* medium confidence: slightly faded,
* low confidence: faded/hatched.

Special areas:

* bridge icon/line,
* tunnel/underpass low-confidence symbol,
* high-rise cluster warning,
* river corridor label,
* gust-transition marker.

E. Animation rules

Particles should:

* move according to u/v field,
* not pass through buildings,
* slow/fade in sheltered zones,
* move faster in high-speed corridors,
* show jitter only where turbulence/uncertainty is expected.

Do not:

* create decorative swirls everywhere,
* imply exact turbulence,
* hide static score layer.

============================================================
11. VALIDATION REQUIREMENTS
===========================

A. v0.1 validation

Manual plausibility check:

* 20–50 points.
* Check against expected geometry behavior.
* No public accuracy claim.

B. v0.2 validation

Local sanity dataset:

* bridges,
* quays,
* squares,
* sheltered streets,
* high-rise zones,
* slopes.

C. v0.4 validation

Formal benchmarks:

* 5–10 benchmark cases.
* low/medium/high classification.
* confusion matrix.
* high-wind recall.
* top-20% overlap.
* baseline comparison.

D. Success threshold

Minimum useful product target:

* 70–80% overall classification accuracy,
* at least 80% high-wind recall,
* 60–70% high-wind precision,
* at least 90% adjacent-class accuracy.

E. Public claims

Before validation:
“Estimated exposure screening.”

After validation:
“Validated on selected benchmark cases for relative high/medium/low wind-zone classification.”

Never claim:
“Certified CFD accuracy.”

============================================================
12. NON-FUNCTIONAL REQUIREMENTS
===============================

Performance:

* v0.1 scenario response under 3 seconds for selected district.
* v0.2 cached scenarios under 1 second.
* map initial load under 5 seconds.
* vector animation 30 fps target on modern desktop.
* mobile support should prioritize static layers over heavy animation.

Scalability:

* support one district in v0.1,
* full Lyon in v0.5,
* multiple French cities in v1.1.

Reliability:

* weather fetch failure should fall back to last cached data,
* data-source version should be stored,
* model version should be stored with each result.

Reproducibility:
Every result must be traceable to:

* data version,
* model version,
* weather source,
* timestamp,
* selected wind input.

Security:

* standard web app security,
* no sensitive personal data required,
* user feedback can be anonymous.

Accessibility:

* avoid color-only interpretation,
* include labels/patterns,
* keyboard navigable controls,
* readable contrast.

Localization:

* initial product can be English.
* French UI should be supported for Lyon/French municipalities.

============================================================
13. DISCLAIMERS AND TRUST LANGUAGE
==================================

Always include an accessible explanation:

“This tool estimates relative wind exposure using regional wind data and urban geometry. It is intended for early screening and exploration. It is not a substitute for CFD, wind tunnel testing, certified pedestrian wind comfort studies, or on-site safety assessment.”

For animation:
“Animated airflow shows approximate mean-flow direction and strength derived from the model. It is not a real-time turbulent CFD simulation.”

For low-confidence zones:
“Geometry or source data is insufficient for a confident estimate here.”

For tunnels:
“Tunnel interior airflow is not modeled in this version.”

============================================================
14. MAJOR RISKS
===============

Risk 1:
Animation creates false trust.

Mitigation:
Only add animation after vector field exists. Always show confidence and explanatory labels.

Risk 2:
Building height data incomplete.

Mitigation:
Use official data first. Store height source. Use fallback model. Lower confidence.

Risk 3:
Special geometries break simple scoring.

Mitigation:
Use handling modes:

* normal_score,
* special_rule,
* low_confidence,
* excluded.

Risk 4:
Model not validated.

Mitigation:
Formal v0.4 validation before strong claims.

Risk 5:
Weather API misunderstood.

Mitigation:
Explain that weather API gives regional/reference wind, not street wind.

Risk 6:
Users want engineering certification.

Mitigation:
Clear disclaimers, professional report wording, and optional recommendation to commission CFD.

Risk 7:
Performance problems with vector fields.

Mitigation:
Precompute directions, use vector tiles/rasters, limit high-res grids to selected zones.

Risk 8:
Vegetation modeling too weak.

Mitigation:
Treat vegetation as minor modifier until better data exists.

Risk 9:
Terrain in Lyon causes errors.

Mitigation:
Add DEM terrain modifier by v0.2/v0.5 and lower confidence on steep complex areas.

Risk 10:
Official data licensing/format complexity.

Mitigation:
Start with one city/district. Build repeatable ETL. Track licenses and attribution.

============================================================
15. KEY OPEN QUESTIONS
======================

1. What exact Lyon district should be the v0.1 pilot?

Recommendation:
Presqu’île + river quays + nearby bridges.

2. What is the actual building-height coverage in Lyon?

Action:
Run audit across:

* BD TOPO,
* BDNB,
* Grand Lyon 3D,
* OSM.

3. Which source gives best building height for Lyon?

Likely:
Grand Lyon / BD TOPO first, BDNB enrichment.

4. Should v0.1 be street-based or grid-based?

Recommendation:
v0.1 street-based + special polygons.
v0.2 add coarse grid.
v0.3 vector grid.

5. Should we use URock directly in product?

Recommendation:
Use it first as research/prototype engine. Later decide whether to productize or build internal solver.

6. What is acceptable accuracy for first commercial pilots?

Recommendation:
Do not sell exact speed. Sell high/medium/low screening with clear validation.

7. What is the best validation dataset to start with?

Recommendation:
AIJ/Niigata or URock-compatible benchmark first, then local Lyon field checks.

8. How should confidence affect UI?

Recommendation:
Low-confidence areas should be visually obvious, not hidden in details.

9. Should public users see uncertainty?

Yes. It builds trust and protects the product.

10. Should we support mobile?

Yes for viewing; heavy animation can be desktop-first.

============================================================
16. IMMEDIATE NEXT STEPS
========================

Step 1:
Choose v0.1 pilot zone in Lyon.

Recommended:
Presqu’île + Rhône/Saône edges + 3–5 bridges.

Step 2:
Run data audit.

Measure:

* total buildings,
* buildings with official height,
* buildings with fallback height,
* road completeness,
* bridge detection,
* river/quay detection,
* vegetation completeness,
* terrain availability.

Step 3:
Build static feature pipeline.

Compute:

* street orientation,
* estimated width,
* H/W ratio,
* river proximity,
* bridge flag,
* open-space proximity,
* upwind shielding,
* vegetation presence,
* special geometry type,
* confidence.

Step 4:
Implement v0.1 scoring.

Start with manual wind direction/speed.

Step 5:
Build map UI.

Show:

* exposure colors,
* confidence,
* explanations.

Step 6:
Manual validation.

Test:

* bridges,
* quays,
* squares,
* sheltered streets,
* old narrow streets,
* high open areas.

Step 7:
Add Open-Meteo.

Move from manual-only to current/forecast mode.

Step 8:
Prototype URock on same district.

Compare:

* scalar score vs URock vector field,
* whether vector field reveals missing effects.

Step 9:
Prepare validation plan.

Pick benchmark cases and define metrics.

Step 10:
Decide whether to continue with scalar-first or vector-first product path.

============================================================
17. FINAL PRODUCT DEFINITION
============================

The product should evolve like this:

v0.1:
A credible static wind exposure map for one Lyon district.

v0.2:
A weather-connected Lyon beta with better scoring and special geometry handling.

v0.3:
A vector-field airflow visualization based on diagnostic urban wind modeling.

v0.4:
A formally validated model with clear accuracy metrics.

v0.5:
A full Lyon beta covering rivers, bridges, hills, old districts, high-rises, and open spaces.

v1.0:
A commercial urban wind screening product for professionals.

v1.1:
A scalable France-wide city onboarding pipeline.

v2.0:
An advanced internal wind-field engine, potentially supported by diagnostic modeling, sensors, and ML surrogates.

The core strategic decision:
Start simple, but not simplistic.

The MVP should be static and explainable. The later product can be animated and sophisticated. The model must always be honest about what it knows, what it estimates, and where it is uncertain.

[1]: https://open-meteo.com/en/docs?utm_source=chatgpt.com "Weather Forecast API"
[2]: https://gmd.copernicus.org/articles/16/5703/2023/?utm_source=chatgpt.com "URock 2023a: an open-source GIS-based wind model ... - GMD"
[3]: https://inspire-geoportal.ec.europa.eu/srv/api/records/IGNF_BD-TOPO?utm_source=chatgpt.com "BD TOPO® - INSPIRE Geoportal"
[4]: https://www.maplibre.org/maplibre-gl-js/docs/examples/?utm_source=chatgpt.com "Overview - MapLibre GL JS"
[5]: https://www.cityoflondon.gov.uk/assets/Services-Environment/wind-microclimate-guidelines.pdf?utm_source=chatgpt.com "Wind Microclimate Guidelines"
[6]: https://pythongis.org/part2/chapter-09/nb/00-retrieving-osm-data.html?utm_source=chatgpt.com "Retrieving OpenStreetMap data"
