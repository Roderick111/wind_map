# Wind Flow UI Vision and Implementation Plan

Date: 2026-07-01

## Purpose

The wind map should not only color places as low, medium, high, or very high exposure. It should also have a real flow view: animated, endless, street-level "meteor" traces that move along each street, quay, bridge, and open corridor in the model's estimated local flow direction.

The reference visual is a weather-map wind animation, but applied at urban street scale. Instead of broad regional streaks over terrain, the app should show small moving streaks traveling through the normalized street/corridor network.

For v0.5, this is still not CFD. But it is more than static arrows. We should compute a lightweight local street-flow field from wind direction, street geometry, open corridors, special rules, shielding, and confidence. The flow view then animates that computed field.

The UI claim should be:

> Approximate street-level flow paths inferred from wind direction, urban geometry, and model confidence.

Not:

> Real turbulent airflow simulation.

## Product Principle

Flow UI should make the model feel alive and legible while staying honest about what is computed.

The flow view is allowed to animate, but only from a computed local flow model. It must not animate random decorative particles.

Good flow UI:

- uses one normalized flow path per street/corridor, not the current duplicated exposure lines;
- shows endless meteor streaks moving in the estimated local direction;
- makes speed, density, opacity, and color reflect model outputs;
- shows uncertainty by fading, slowing, or suppressing meteors;
- explains why a street, quay, bridge, or square has that flow direction;
- makes complex zones visibly model-limited.

Bad flow UI:

- decorative particles with no computed flow field;
- swirls that imply turbulence we did not compute;
- three overlapping animated lines for the same street;
- animation over building polygons as if buildings were passable;
- dense streaks that obscure the map;
- treating every street as if wind follows it exactly.

Important distinction:

- `exposure view` can keep the current colored geometry.
- `flow view` must use normalized single centerlines/corridors.

## User Experience Vision

The user opens the map, selects a wind direction and speed, and sees the normal exposure layer. When they enable "Flow view", the map changes emphasis:

- exposure colors become quieter;
- normalized street/corridor paths become the main visual surface;
- small endless meteor streaks move along each eligible path;
- faster/brighter/more frequent meteors indicate stronger estimated local flow;
- faded or sparse meteors indicate uncertainty or weak flow;
- bridges, quays, and river corridors show clearer movement when exposed;
- high-rise clusters, tunnels, underpasses, and complex hill/street interactions show model-limited treatment instead of confident animation.

When the user clicks a feature, the explanation panel shows the local flow interpretation in plain language:

- "Wind likely channels along this street."
- "Wind crosses this bridge from the side, increasing pedestrian/cyclist discomfort."
- "This quay is exposed because wind aligns with the river corridor."
- "Scalar model is limited here; high-rise downwash and corner effects need vector modeling."

## Flow View Design

Add a new layer group called `Flow view`.

It should contain five internal layers, but the UI can expose them as one toggle first.

### 1. Global Wind Indicator

Purpose:

- Always orient the user.

Display:

- compact compass/arrow overlay in the map corner;
- direction label, e.g. `NW wind`, `354 deg`;
- speed and gust summary if available.

Behavior:

- updates with manual/current/forecast mode;
- does not depend on selected map feature.

### 2. Normalized Flow Paths

Purpose:

- Fix the current visual problem where streets often render as three lines or duplicated overlays.
- Provide one clean animation path per street/corridor in flow mode.

Why this matters:

- Exposure geometry can be duplicated because roads, buildings, special features, and cached tiles overlap.
- Flow animation cannot use that raw visual stack.
- A meteor layer needs a clean centerline graph.

Data shape:

- `flow_path_id`
- `source_feature_ids`
- `path_type`
  - `street`
  - `quay`
  - `bridge`
  - `river_corridor`
  - `open_exit`
- `geom`
- `length_m`
- `base_bearing_deg`
- `canonical_name`
- `confidence`

Normalization rules:

- merge duplicate/parallel street features that represent the same corridor;
- prefer road/street centerlines over polygon edges;
- keep bridge and quay paths as special path types;
- split long paths at intersections so flow can change direction locally;
- remove tiny duplicate segments below a configured length threshold;
- keep enough topology to animate through intersections.

Acceptance criteria:

- in flow view, each visible street/corridor has one clean animated path;
- Place Guichard-like areas no longer show three competing flow lines for the same street;
- bridge/quay paths remain distinct where they represent genuinely different flow contexts.

### 3. Street Meteor Animation

Purpose:

- Show local flow as endless moving streaks along normalized paths.

Eligible features:

- normalized street flow paths;
- quays;
- bridges;
- river-corridor paths;
- open-exit transition paths.

Rules:

- meteor direction follows computed local flow direction, not just the global wind arrow;
- meteor speed follows estimated local speed/multiplier;
- meteor density follows risk score or flow strength;
- meteor opacity follows confidence;
- meteor color can follow exposure class, but should be less saturated than the exposure map;
- weak/uncertain paths get fewer, slower, faded meteors;
- excluded/tunnel interiors get no meteors;
- vector-preferred zones can show limited scalar meteors only if clearly labeled as low-confidence.

Visual style:

- short tapered streaks, like the weather-map reference;
- repeated along the path with staggered phase offsets;
- fade in/out at segment ends;
- do not cover labels or buildings heavily;
- hidden or simplified at low zoom;
- optionally use a canvas/WebGL layer for smooth animation.

Recommended v0.5 implementation:

- generate normalized flow paths first;
- compute per-path flow values for the selected wind scenario;
- render in frontend using a custom Canvas/WebGL overlay, or a MapLibre animated line-gradient/dash fallback;
- store or return:
  - `flow_path_id`
  - `source_feature_ids`
  - `flow_direction_deg`
  - `flow_strength`
  - `flow_speed_px_s`
  - `meteor_density`
  - `confidence`
  - `flow_type`
  - `reason`
- animation phase should be client-side only; model values come from backend.

### 4. Bridge Crosswind Warnings

Purpose:

- Make bridge discomfort understandable, especially for pedestrians and cyclists.

Eligible features:

- `bridge`

Rules:

- if wind is roughly perpendicular to bridge path, show a crosswind indicator;
- if wind aligns with river corridor and bridge is exposed, show both river-corridor exposure and crosswind/cyclist warning where applicable;
- avoid claiming exact danger.

Visual style:

- small warning chevron or side-arrow centered on bridge;
- magenta/purple only when gust layer is enabled or gust-sensitive;
- otherwise use exposure color with a crosswind icon.

Explanation text:

- "Crosswind to bridge path may feel uncomfortable for pedestrians/cyclists."

### 5. Open-Exit / Gust-Transition Markers

Purpose:

- Highlight places where wind exposure changes suddenly.

Examples:

- dense old street exiting to a quay;
- side street opening to a large square;
- bridge landing;
- sheltered canyon opening into river corridor.

Eligible features:

- `open_exit_transition`
- street/quay/bridge relationships with relevant cause tags

Rules:

- show where the score has transition/gust tags;
- make marker subtle unless risk is high.

Visual style:

- small triangular or split-arrow marker;
- tooltip: "Exposure transition";
- explanation panel gives the real reason.

## Lightweight Street-Flow Simulation

The meteor animation needs a small simulation step. It should not just project the global wind arrow onto every street. It should estimate a plausible local flow direction and strength for each normalized path.

This is a graph-based diagnostic approximation, not CFD.

### Inputs

- global wind direction and speed;
- normalized flow path bearing;
- path type: street, quay, bridge, river corridor, open exit;
- directional alignment;
- H/W canyon ratio;
- enclosure ratio;
- nearby high-rise score;
- river distance and river-axis alignment;
- upwind shielding;
- open fetch;
- vegetation;
- slope/aspect when available;
- special geometry type;
- confidence and handling mode.

### Per-Path Local Flow Direction

Each path should get:

- `flow_direction_deg`
- `reverse_flow_possible`
- `flow_strength`
- `flow_confidence`

Rules:

- If a street is strongly aligned with wind, flow follows the street in the downwind direction.
- If a street is perpendicular to wind, flow is weak or suppressed unless special geometry suggests cross-flow.
- If a quay/river corridor aligns with wind, flow follows the river axis downwind.
- If a bridge is exposed, flow can show either along-bridge movement or crosswind marker depending on wind/bridge angle.
- If an open-exit transition exists, flow should point from sheltered fabric toward the exposed opening only when wind direction supports it.
- If local geometry is complex, reduce confidence and meteor density instead of inventing precise flow.

### Intersection Relaxation

At intersections, the flow should not look like unrelated streaks colliding randomly.

Implement a simple graph propagation:

- build nodes at intersections and edges from normalized flow paths;
- assign each edge a base wind projection score;
- let wind energy continue into outgoing edges that are directionally compatible;
- reduce energy sharply for hard turns unless channeling/special rules support the turn;
- increase energy into open exits, quays, bridges, and aligned corridors;
- dampen energy behind shielding and in low-confidence features;
- run 2-4 relaxation passes, not an expensive solver.

Output:

- edge flow direction;
- edge flow speed class;
- edge meteor density;
- edge confidence;
- cause tags for why the flow was chosen.

This gives the UI a coherent "moving through streets" feel without pretending to solve Navier-Stokes equations.

### Meteor Parameters

Map model values to animation:

- `flow_strength` -> meteor speed;
- `risk_score` -> meteor brightness and density;
- `confidence` -> opacity and continuity;
- `gust_sensitive` -> occasional brighter pulses when gust layer is enabled;
- `handling_mode=vector_preferred` -> sparse dashed meteors plus warning badge;
- `handling_mode=excluded` -> no meteors.

## Flow Data Modes

The UI must distinguish three modes:

1. Scalar exposure view.
2. Lightweight street-flow meteor view.
3. Computed vector field view.

### Scalar Exposure View

This is the current colored risk map.

It can show:

- exposure colors;
- confidence;
- special geometry;
- gust risk;
- labels.

It cannot show:

- animated flow.

### Lightweight Street-Flow Meteor View

This is the target v0.5 flow UI.

It can show:

- normalized street/corridor paths;
- endless meteor streaks along those paths;
- bridge crosswind markers;
- open-exit transition pulses;
- confidence fading;
- model-limited badges.

It cannot show:

- free-field particles moving across buildings;
- turbulent swirls;
- continuous CFD streamlines;
- exact wake behavior behind buildings.

### Computed Vector Field

This is future/selected-zone behavior, only available where `vector_field_metadata` exists.

It can show:

- vector arrows from `u/v` values;
- streamlines;
- particles following vectors;
- local speed grid;
- confidence fade.

Rules:

- regional/free-field animation remains disabled unless vector field data exists;
- tooltip must say "Approximate mean airflow";
- vector field layer must include model source and confidence;
- vector particles must not appear in scalar-only zones.

## Data Requirements

The current backend already exposes most inputs needed for first-pass flow UI:

- feature geometry;
- feature type;
- risk score;
- exposure class;
- confidence;
- handling mode;
- sub-scores;
- cause tags;
- directional cache;
- vector zones.

Need to add two derived outputs:

### `flow_paths`

Normalized path geometry for animation.

Recommended fields:

- `id`
- `area_id`
- `source_feature_ids_json`
- `path_type`
- `name`
- `geom`
- `length_m`
- `bearing_deg`
- `from_node_id`
- `to_node_id`
- `confidence`
- `created_at`

### `flow_path_nodes`

Graph nodes for intersections and path endpoints.

Recommended fields:

- `id`
- `area_id`
- `geom`
- `node_type`
- `connected_path_ids_json`

### `flow_indicators`

This can be an API response first, then a cached table if performance requires it.

Recommended fields:

- `id`
- `scenario_run_id` or cache key
- `flow_path_id`
- `source_feature_ids`
- `indicator_type`
  - `street_meteor`
  - `river_corridor_arrow`
  - `bridge_crosswind`
  - `open_exit_transition`
  - `model_limited`
- `geom`
- `flow_direction_deg`
- `flow_strength`
- `confidence`
- `exposure_class`
- `reason`
- `source`
  - `scalar_alignment`
  - `special_rule`
  - `directional_cache`
  - `vector_field`
- `model_note`

For PMTiles mode, generate:

- `flow_paths.pmtiles`
- `flow_indicators_{direction}.pmtiles`

## Backend Plan

### Phase 1: Flow Path Normalization

Create a service that builds clean animation paths from existing spatial features.

Inputs:

- `spatial_features`
- `computed_feature_metrics`
- bridge/quay/special geometry types
- feature relationships if available

Logic:

- select street/quay/bridge/open-exit geometries;
- merge duplicated or near-parallel same-name/same-corridor paths;
- split at intersections;
- create graph nodes;
- preserve source feature ids for click/explanation lookup;
- mark paths that should not animate.

CLI:

- `make build-flow-paths AREA=pilot_presquile`
- `make build-flow-paths AREA=lyon_full`

Acceptance criteria:

- pilot flow paths render one centerline per street/corridor;
- duplicated three-line street rendering is gone in flow mode;
- paths preserve bridge/quay distinctions.

### Phase 2: Street-Flow Simulation Service

Create a service that computes flow values for each normalized path.

Inputs:

- scenario wind direction;
- scenario wind speed and gust;
- normalized flow path graph;
- source feature metrics;
- scalar result;
- cause tags;
- handling mode;

Logic:

- compute base wind projection onto each path;
- choose downwind direction along path geometry;
- apply special rules for bridges, quays, river corridors, open exits, high-rise clusters, and tunnels;
- run 2-4 graph relaxation passes through intersections;
- compute meteor speed, density, opacity, confidence, and reason tags;
- suppress animation for excluded features;
- mark vector-preferred areas as low-confidence scalar flow.

API:

- `GET /areas/{slug}/flow?wind_direction_deg=&wind_speed_ms=&wind_gust_ms=`
- optional `direction=` cache form for PMTiles mode.

Acceptance criteria:

- pilot area returns normalized flow paths with animation parameters;
- low-confidence/excluded features do not receive misleading meteors;
- bridges/quays/open exits get special flow treatment;
- each flow path includes a plain-language reason.

### Phase 3: Tile Generation

For full Lyon, avoid huge live GeoJSON.

Add tile generation:

- `flow_paths.pmtiles`
- `flow_0.pmtiles`
- `flow_22.pmtiles`
- `flow_45.pmtiles`
- etc.

Rules:

- include normalized paths and direction-specific animation parameters;
- simplify paths at low zoom;
- avoid generating multiple paths for the same corridor;
- keep selected feature explanation API live.

Acceptance criteria:

- full Lyon flow layer loads through PMTiles;
- meteors do not clutter at city zoom;
- flow tiles stay direction-specific and model-versioned.

### Phase 4: Vector Field Integration Hook

Do not implement full vector fields here. Prepare the UI contract.

When `vector_field_metadata` exists for a zone:

- expose layer availability;
- enable vector-field particles/streamlines only inside that zone;
- show source model and confidence.

Acceptance criteria:

- Part-Dieu/Confluence can show "vector field not available yet";
- future vector field data can be added without redesigning the UI.

## Frontend Plan

### Phase 1: Flow Mode Toggle and Global Indicator

Add to `LayerMenu`:

- `Flow view`

Add map overlay:

- global wind arrow;
- wind direction/speed/gust label.

Behavior:

- when enabled, exposure layer opacity is reduced;
- normalized flow paths become the main visual layer;
- labels and confidence remain optional overlays.

Acceptance criteria:

- user can tell wind direction without reading controls;
- toggle clearly switches to flow-mode emphasis.

### Phase 2: Normalized Flow Path Layer

Add source:

- `flow-paths`

Add layers:

- quiet base path line;
- selected path highlight;
- model-limited path/badge layer.

Rules:

- render one centerline per flow path;
- do not render raw duplicated exposure geometries in flow mode;
- hide paths below zoom thresholds if needed.

Acceptance criteria:

- the flow map is visually clean before meteors are added;
- streets no longer show three parallel flow lines.

### Phase 3: Meteor Animation Layer

Render endless meteor streaks along normalized paths.

Preferred implementation:

- custom Canvas/WebGL overlay synchronized with MapLibre camera;
- project path coordinates to screen each frame;
- place repeated short streaks along each path;
- animate phase offset with `requestAnimationFrame`;
- use backend-provided speed/density/confidence values.

Fallback implementation:

- MapLibre line layers with animated `line-dasharray` or changing gradient where feasible;
- acceptable for prototype, but likely less smooth.

Meteor visual mapping:

- speed -> movement rate;
- risk/flow strength -> density and brightness;
- confidence -> opacity and continuity;
- gust sensitivity -> occasional pulse;
- model-limited -> sparse dashed streaks or badge.

Acceptance criteria:

- meteors move continuously along each street/corridor;
- meteor direction changes with wind direction;
- no meteors move through buildings or across unrelated areas;
- animation remains smooth on pilot area.

### Phase 4: Bridge, Exit, and Limited-Zone Markers

Add marker layers:

- bridge crosswind marker;
- open-exit/gust-transition marker;
- vector-preferred/model-limited badge.

Acceptance criteria:

- bridge warnings are visible without overwhelming meteors;
- model-limited zones are clear;
- markers explain exceptions where meteor flow is uncertain.

### Phase 5: Explanation Panel Flow Section

Add a `Street flow` section when a selected feature has flow values or relevant cause tags.

Show:

- local flow interpretation;
- computed path direction;
- why meteors move that way;
- flow strength;
- meteor confidence;
- confidence;
- limitation if scalar street-flow only.

Example:

```text
Street flow
Meteors move east along this corridor because the selected wind aligns with the street and the canyon ratio supports channeling.
Confidence: medium.
```

For bridge:

```text
Street flow
This bridge is exposed. The local flow model shows side-wind pressure across the crossing, which can feel uncomfortable for pedestrians and cyclists during gusts.
```

Acceptance criteria:

- selected feature explains the meteor direction;
- text avoids CFD language;
- vector-preferred zones clearly state scalar limitations.

### Phase 6: Selected Feature Context

When a feature is selected:

- emphasize the selected normalized flow path;
- show upwind/downwind direction along the path;
- optionally dim unrelated meteors;
- show connected paths at nearby intersections.

Acceptance criteria:

- user can understand why one selected feature was scored high;
- selected context does not clutter the whole map.

## Visual Design Guidelines

The map should stay usable as a planning tool.

Rules:

- flow mode uses normalized paths and meteors as the primary visual language;
- exposure color becomes a subdued supporting layer in flow mode;
- meteors should be sparse enough to read the street network;
- no free-field particle layer in scalar street-flow mode;
- no animated swirls;
- low-confidence flow should fade or show a warning badge;
- bridges/quays/squares need recognizable but restrained markers;
- labels should not overlap meteors at normal zoom.

Recommended hierarchy:

1. Normalized flow paths and meteors.
2. Selected feature highlight.
3. Exposure color as supporting context.
4. Confidence/limitations.
5. Bridge/exit/model-limited markers.
6. Labels.

## Scoring and Flow Relationship

Flow UI must be derived from the scoring model, not from separate decorative logic.

Use:

- `directional_alignment`;
- `m_alignment`;
- `m_open`;
- `m_special_geometry`;
- `handling_mode`;
- `cause_tags`;
- `confidence`;
- `river_axis_deg`;
- `corridor_orientation_deg`;
- bridge orientation.

Examples:

- `wind_aligned_corridor` -> faster/brighter street meteors.
- `river_aligned_wind` -> stronger quay/river corridor meteors.
- `crosswind_discomfort` -> bridge crosswind marker.
- `open_exit_transition` -> transition pulse marker.
- `vector_model_preferred` -> model-limited badge.

This keeps visual flow and scoring explanations consistent.

## Testing Plan

### Backend Tests

- normalized flow paths merge duplicated same-corridor street lines;
- aligned high-confidence street produces meteor flow values;
- perpendicular street produces weak/suppressed meteor values;
- river corridor path strengthens when wind aligns with river;
- bridge crosswind marker appears for crosswind bridge;
- excluded/tunnel features produce model-limited markers only;
- low confidence suppresses or fades meteors;
- flow reasons match cause tags.

### Frontend Tests

- layer toggle switches exposure view and flow view;
- global wind indicator updates with wind controls;
- selected feature panel shows street-flow text;
- meteor animation starts/stops cleanly;
- meteors change direction when wind direction changes;
- PMTiles mode and GeoJSON mode both support flow layer;
- free-field/vector animation controls remain disabled when no vector field exists.

### Visual QA

Check at:

- pilot Presqu'ile desktop;
- pilot Presqu'ile mobile;
- full Lyon city zoom;
- bridge/quay zoom;
- dense old-street zoom;
- vector-preferred zone zoom.

Acceptance:

- one normalized path appears per street/corridor in flow mode;
- meteors are readable but not noisy;
- text and controls do not overlap;
- selected context is understandable;
- scalar street-flow visual language does not imply CFD.

## Implementation Order

1. Add this plan to docs.
2. Add backend flow-path normalization service.
3. Add backend street-flow simulation service.
4. Add live GeoJSON flow endpoint for pilot development.
5. Add `Flow view` toggle and global wind indicator.
6. Render normalized flow paths on pilot map.
7. Add Canvas/WebGL meteor animation over normalized paths.
8. Add explanation-panel street-flow section.
9. Add backend tests for path normalization and flow simulation.
10. Add frontend tests/build verification.
11. Add PMTiles generation for full-Lyon flow paths and direction-specific flow values.
12. Add selected-feature context highlighting.
13. Add vector-field UI hook, still disabled until vector data exists.

## Definition of Done

Wind flow UI is done for v0.5 when:

- users can see the selected regional wind direction on the map;
- flow view renders one normalized path per street/corridor instead of duplicated exposure lines;
- high-confidence aligned corridors show endless meteor streaks moving in the estimated local direction;
- meteor speed/density/opacity reflect flow strength and confidence;
- bridges show crosswind discomfort when relevant;
- river/quay corridors show stronger directional meteor flow when relevant;
- open-exit transitions are visually pulsed/marked;
- vector-preferred and low-confidence zones are visibly model-limited;
- explanation panel describes the likely flow in plain language;
- no free-field particles or fake turbulent streamlines appear without vector data;
- full Lyon can use tiled normalized flow paths without performance collapse.

## Non-Goals

- No CFD visualization.
- No turbulent animation.
- No free-field particle layer without computed vector fields.
- No meteor animation on raw duplicated street/exposure geometry.
- No exact local flow speed claim.
- No confident meteors for every street regardless of geometry.
- No hiding uncertainty behind impressive visuals.
