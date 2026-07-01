# Wind Flow UI Vision and Implementation Plan

Date: 2026-07-01

## Purpose

The wind map should not only color places as low, medium, high, or very high exposure. It should also help the user understand how wind is likely interacting with the city: where it aligns with streets, follows river corridors, crosses bridges, exits sheltered streets into open spaces, and becomes uncertain in complex zones.

For v0.5, this must remain a screening UI. We are not showing CFD. We are showing model-derived flow interpretation from scalar scoring, directional metrics, special geometry rules, and later true vector fields where available.

The UI claim should be:

> Likely wind-flow patterns inferred from wind direction, urban geometry, and model confidence.

Not:

> Real turbulent airflow simulation.

## Product Principle

Flow UI should make the scalar model easier to understand, not make it look more physically precise than it is.

Good flow UI:

- explains why a street, quay, bridge, or square is exposed;
- shows the relationship between reference wind direction and local geometry;
- distinguishes strong evidence from uncertainty;
- makes complex zones visibly model-limited;
- stays consistent with exposure colors and explanation tags.

Bad flow UI:

- decorative particles with no vector field;
- swirls that imply turbulence we did not compute;
- dense arrows that obscure the exposure layer;
- animation in scalar-only zones;
- treating every street as if wind follows it exactly.

## User Experience Vision

The user opens the map, selects a wind direction and speed, and sees the normal exposure layer. When they enable "Flow interpretation", the map adds restrained directional cues:

- a global wind direction indicator;
- arrows along high-confidence street corridors where wind alignment is strong;
- river/quay corridor arrows where wind aligns with the Rhone or Saone;
- crosswind warning arrows on bridges;
- open-exit markers where sheltered streets meet quays, bridges, or squares;
- model-limited badges for high-rise clusters, tunnels, underpasses, and complex hill/street interactions.

When the user clicks a feature, the explanation panel shows the local flow interpretation in plain language:

- "Wind likely channels along this street."
- "Wind crosses this bridge from the side, increasing pedestrian/cyclist discomfort."
- "This quay is exposed because wind aligns with the river corridor."
- "Scalar model is limited here; high-rise downwash and corner effects need vector modeling."

## Layer Design

Add a new layer group called `Flow interpretation`.

It should contain four visual sublayers, but the UI can expose them as one toggle first.

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

### 2. Corridor Flow Arrows

Purpose:

- Show where the model believes wind can travel along a street, quay, or river corridor.

Eligible features:

- `street_segment`
- `quay`
- `bridge`
- selected `open_exit_transition`

Rules:

- only show if confidence is medium/high;
- only show if directional alignment is strong enough;
- only show for medium/high/very-high exposure unless user enables debug mode;
- arrow opacity follows confidence;
- arrow size follows risk score or local multiplier;
- arrow color follows exposure class, not a separate rainbow scale.

Visual style:

- short arrow glyphs placed along line features;
- sparse enough to avoid clutter;
- line-aligned, not screen-aligned;
- hidden at low zoom;
- stronger arrows on high/very-high features.

Recommended v0.5 implementation:

- generate arrow point features from line centroids or sampled line points;
- store or return:
  - `feature_id`
  - `flow_direction_deg`
  - `flow_strength`
  - `confidence`
  - `flow_type`
  - `reason`
- render as MapLibre symbol layer using an arrow icon and `icon-rotate`.

### 3. Bridge Crosswind Warnings

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

### 4. Open-Exit / Gust-Transition Markers

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

## Vector Field Display Rules

The UI must distinguish two modes:

1. Scalar flow interpretation.
2. Computed vector field.

### Scalar Flow Interpretation

This is available in v0.5.

It can show:

- corridor arrows;
- bridge crosswind direction;
- river/quay alignment;
- special geometry markers;
- uncertainty/model-limited badges.

It cannot show:

- particles;
- continuous streamlines;
- building wake animation;
- turbulence animation.

### Computed Vector Field

This is only available where `vector_field_metadata` exists.

It can show:

- vector arrows from `u/v` values;
- streamlines;
- particles following vectors;
- local speed grid;
- confidence fade.

Rules:

- animation toggle remains disabled unless vector field data exists;
- tooltip must say "Approximate mean airflow";
- vector field layer must include model source and confidence;
- particles must not appear in scalar-only zones.

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

Need to add one derived output:

### `flow_indicators`

This can be an API response first, then a cached table if performance requires it.

Recommended fields:

- `id`
- `scenario_run_id` or cache key
- `feature_id`
- `indicator_type`
  - `corridor_arrow`
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

For PMTiles mode, generate `flow_indicators_{direction}.pmtiles` later.

## Backend Plan

### Phase 1: Scalar Flow Indicator Service

Create a service that converts existing scenario results into flow indicators.

Inputs:

- scenario wind direction;
- feature geometry;
- feature metrics;
- scalar result;
- cause tags;
- handling mode;

Logic:

- street/quay arrows when alignment is strong and confidence is acceptable;
- bridge crosswind markers when bridge orientation is near perpendicular to wind;
- river corridor arrows when river axis aligns with wind;
- transition markers for `open_exit_transition` and relevant cause tags;
- model-limited markers for `vector_preferred`, `low_confidence`, `excluded`.

API:

- `GET /areas/{slug}/flow?wind_direction_deg=&wind_speed_ms=&wind_gust_ms=`
- optional `direction=` cache form for PMTiles mode.

Acceptance criteria:

- pilot area returns sparse, readable indicators;
- low-confidence/excluded features do not receive misleading flow arrows;
- each indicator includes a plain-language reason.

### Phase 2: Tile Generation

For full Lyon, avoid huge live GeoJSON.

Add tile generation:

- `flow_0.pmtiles`
- `flow_22.pmtiles`
- `flow_45.pmtiles`
- etc.

Rules:

- only include indicators above visibility threshold;
- simplify/sparsify at low zoom;
- keep selected feature explanation API live.

Acceptance criteria:

- full Lyon flow layer loads through PMTiles;
- arrows do not clutter at city zoom;
- flow tiles stay direction-specific and model-versioned.

### Phase 3: Vector Field Integration Hook

Do not implement full vector fields here. Prepare the UI contract.

When `vector_field_metadata` exists for a zone:

- expose layer availability;
- enable vector arrows or animation only inside that zone;
- show source model and confidence.

Acceptance criteria:

- Part-Dieu/Confluence can show "vector field not available yet";
- future vector field data can be added without redesigning the UI.

## Frontend Plan

### Phase 1: Flow Toggle and Global Indicator

Add to `LayerMenu`:

- `Flow interpretation`

Add map overlay:

- global wind arrow;
- wind direction/speed/gust label.

Acceptance criteria:

- user can tell wind direction without reading controls;
- toggle does not affect exposure layer.

### Phase 2: Flow Indicator Layer

Add source:

- `flow-indicators`

Add layers:

- `flow-arrow-symbols`
- `flow-transition-markers`
- `flow-limited-markers`

Use MapLibre symbol layers:

- arrow icon;
- `icon-rotate` from `flow_direction_deg`;
- `icon-size` from `flow_strength`;
- opacity from `confidence`;
- color from `exposure_class`.

Acceptance criteria:

- aligned high-risk streets show arrows;
- quays and bridges show specific markers;
- low-confidence/model-limited areas show badges instead of arrows.

### Phase 3: Explanation Panel Flow Section

Add a `Likely flow` section when a selected feature has flow indicators or relevant cause tags.

Show:

- local flow interpretation;
- direction relationship;
- why the marker appears;
- confidence;
- limitation if scalar-only.

Example:

```text
Likely flow
Wind likely channels along this street under the selected NW wind.
Confidence: medium. Based on corridor alignment and canyon geometry.
```

For bridge:

```text
Likely flow
Wind crosses this bridge from the side. This can feel uncomfortable for pedestrians and cyclists, especially during gusts.
```

Acceptance criteria:

- selected feature explains the visual marker;
- text avoids CFD language;
- vector-preferred zones clearly state scalar limitations.

### Phase 4: Selected Feature Context

When a feature is selected:

- subtly highlight upwind/downwind direction;
- emphasize related flow indicators near the selected feature;
- optionally dim unrelated arrows.

Acceptance criteria:

- user can understand why one selected feature was scored high;
- selected context does not clutter the whole map.

## Visual Design Guidelines

The map should stay usable as a planning tool.

Rules:

- exposure color remains the primary visual language;
- flow arrows are secondary;
- arrows should be sparse and calm;
- no dense particle field in scalar mode;
- no animated swirls;
- low-confidence flow should fade or show a warning badge;
- bridges/quays/squares need recognizable but restrained markers;
- labels should not overlap arrows at normal zoom.

Recommended hierarchy:

1. Exposure color.
2. Selected feature highlight.
3. Flow indicator arrows/markers.
4. Confidence/limitations.
5. Labels.

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

- `wind_aligned_corridor` -> corridor arrow.
- `river_aligned_wind` -> river/quay corridor arrow.
- `crosswind_discomfort` -> bridge crosswind marker.
- `open_exit_transition` -> transition marker.
- `vector_model_preferred` -> model-limited badge.

This keeps visual flow and scoring explanations consistent.

## Testing Plan

### Backend Tests

- corridor arrow appears for aligned high-confidence street;
- no corridor arrow for perpendicular street;
- river corridor arrow appears when wind aligns with river;
- bridge crosswind marker appears for crosswind bridge;
- excluded/tunnel features produce model-limited markers only;
- low confidence suppresses or fades arrows;
- indicator reasons match cause tags.

### Frontend Tests

- layer toggle shows/hides flow indicators;
- global wind indicator updates with wind controls;
- selected feature panel shows likely-flow text;
- PMTiles mode and GeoJSON mode both support flow layer;
- vector animation controls remain disabled when no vector field exists.

### Visual QA

Check at:

- pilot Presqu'ile desktop;
- pilot Presqu'ile mobile;
- full Lyon city zoom;
- bridge/quay zoom;
- dense old-street zoom;
- vector-preferred zone zoom.

Acceptance:

- arrows are readable but not noisy;
- text and controls do not overlap;
- selected context is understandable;
- scalar-only visual language does not imply CFD.

## Implementation Order

1. Add this plan to docs.
2. Add backend flow-indicator service for live GeoJSON.
3. Add `Flow interpretation` toggle and global wind indicator.
4. Render flow indicator GeoJSON on pilot map.
5. Add explanation-panel likely-flow section.
6. Add backend tests for indicator generation.
7. Add frontend tests/build verification.
8. Add PMTiles flow indicator generation for full Lyon.
9. Add selected-feature context highlighting.
10. Add vector-field UI hook, still disabled until vector data exists.

## Definition of Done

Wind flow UI is done for v0.5 when:

- users can see the selected regional wind direction on the map;
- high-confidence aligned corridors show sparse directional arrows;
- bridges show crosswind discomfort when relevant;
- river/quay corridors show alignment when relevant;
- open-exit transitions are visually marked;
- vector-preferred and low-confidence zones are visibly model-limited;
- explanation panel describes the likely flow in plain language;
- no scalar-only layer uses particles or fake streamlines;
- full Lyon can use tiled flow indicators without performance collapse.

## Non-Goals

- No CFD visualization.
- No turbulent animation.
- No particle layer without computed vector fields.
- No exact local flow speed claim.
- No flow arrows for every street.
- No hiding uncertainty behind impressive visuals.
