# Wind Track — implementation status

Last updated: 2026-07-01

**Scope:** v0.5 beta — Presqu'île pilot + **Lyon full imported**. Screening tool, not CFD.

## Running locally

```bash
make setup          # migrate + import OSM if missing
make dev            # API :8002, map :5181
make test           # isolated test DB — dev data safe

make enrich-heights # BD TOPO + neighborhood median + quay promotion
make validate       # seed + run Presqu'île sanity validation
make pipeline-lyon  # full Lyon: import → enrich → zones → 16-dir → tiles → audit
make generate-tiles AREA=lyon_full DIRECTIONS=16
make import-dem AREA=pilot_presquile          # DEM + slope metrics
make import-dem AREA=lyon_full FORCE=1        # fetch Lyon elevation grid
make import-dem AREA=lyon_full RECOMPUTE=1  # DEM + refresh directional cache
make audit AREA=lyon_full
```

Dev data persists in `data/wind_track.db`.

---

## Implemented

### Data & pipeline

| Item | Status |
|------|--------|
| SQLite schema + migrations | Done |
| Presqu'île OSM import | Done — ~7k features |
| **Lyon full area** (`lyon_full`) | **Done — imported & processed** |
| Import skip-if-present + `FORCE=1` | Done |
| Metrics batch | Done |
| 8-direction precompute cache | Done |
| **16-direction precompute** | Done — Lyon full (3.35M cache entries) |
| **BD TOPO height enrichment** | Done — IGN WFS `BDTOPO_V3:batiment`, centroid match |
| **Quay detection** | Done — `Quai …` name + `man_made` tags at import; `promote_quay_streets()` on import/enrich |
| Neighborhood height fallback | Done — 40 m OSM median for unmatched buildings |
| Optional file patches | Done — `data/heights/{slug}.geojson` |
| **PMTiles** | Done — `make generate-tiles`; served at `/tiles/{slug}/` |
| **Full Lyon pipeline** | Done — `make pipeline-lyon` (~17 min tiles on M-series Mac) |
| **Priority zones** | Done — Vieux Lyon, Fourvière, Croix-Rousse, bridge corridors |
| **Quality audit** | Done — `make audit` |
| **Overpass 3×3 grid + cache** | Done — `data/overpass_cache/lyon_full.json` |
| **French OSM decimal parse** (`8,40`) | Done |

**Presqu'île data quality (after enrich):**

| Metric | Value |
|--------|-------|
| Buildings | ~2 624 |
| Official height (`bdtopo` + `osm_height`) | **~96.5%** |
| Estimated height (`osm_levels`, `neighborhood_median`) | ~0.7% |
| Fallback (`fallback_default`) | ~2.9% |
| Quays | **129** (was 0) |

**Lyon full data quality (2026-07-01 pipeline):**

| Metric | Value |
|--------|-------|
| Features | **209 542** |
| Buildings | 113 032 |
| Official height | **91.8%** |
| Streets | 85 362 |
| Bridges / quays / tunnels | 1 394 / 566 / 526 |
| PMTiles | base + 16 exposure layers ready |
| Cache entries | 3 352 672 |

### Scoring (scalar v0.1)

- Full subscore model + special rules + handling modes
- **Weather gust boost** — Open-Meteo gust/speed ratio raises risk + `gust_sensitive` flag
- Gust wired through cache path (`wind_gust_ms` query param)
- **Large-area guard** — `POST /scenarios/scalar` returns 409 when cache ready + area >10k features

### Validation harness (M11)

| Item | Status |
|------|--------|
| 15 Presqu'île sanity points | Done |
| Baselines: flat / alignment / density / full | Done |
| Confusion matrix + high-wind recall | Done |
| API: `/validation/cases`, `/seed`, `/run`, `/metrics` | Done |
| CLI: `make validate` | Done |
| UI: Validation panel | Done |
| Pilot accuracy | **47% exact, 87% adjacent** — beats all baselines |

### Vector zones (M10 partial)

- Presqu'île + **Part-Dieu** + **Confluence** zone definitions
- Map overlay + `vector_preferred` explanation note
- **Export:** `GET /areas/{id}/vector-zones/{zone_id}/export`

### Backend API (highlights)

| Endpoint | Purpose |
|----------|---------|
| `GET /areas/{slug}/exposure?wind_gust_ms=` | Cached exposure with gust scaling |
| `GET /areas/{slug}/tiles` | PMTiles manifest (exposure + flow) |
| `GET /areas/{slug}/flow` | Scalar flow interpretation indicators |
| `GET /areas/{id}/data-quality` | Official / estimated / fallback height tiers |
| `POST /scenarios/scalar` | Live scoring (409 for large cached areas) |
| `POST /validation/seed` | Seed sanity case |
| `POST /validation/run` | Run baselines + metrics |
| `GET /areas/{id}/vector-zones/{id}/export` | Vector research package |
| `POST /feedback` | User issue reports |

### Frontend

| Feature | Status |
|---------|--------|
| Manual / current / forecast + instant cache | Done |
| **PMTiles map mode** — Lyon full at scale | Done |
| **Building exposure toggle** — streets only by default | Done |
| **Fast direction updates** — swap tile URL, no full rebuild | Done |
| **Map style-load guard** — no crash on Current / layer toggles | Done |
| **Gust layer** — geometry + forecast gusts | Done |
| **Validation panel** | Done |
| **Area selector** (when multiple areas in DB) | Done |
| **Data quality panel** — official / estimated / fallback tiers | Done |
| Lyon defaults — vector zones + labels off (less clutter) | Done |
| Explanation + vector disclaimer | Done |
| About accuracy section | Partial — inline in app, not dedicated page |
| Feedback button | Partial — API wired, minimal UI |
| **Flow interpretation** — compass + corridor/bridge/quay arrows | Done |
| **Likely flow** explanation section | Done |
| **Flow PMTiles** — `flow_{direction}.pmtiles` in tile generation | Done — regenerate tiles to build |
| **Vector field animation hook** — disabled until metadata exists | Done |
| **Selected-feature flow context** — dim unrelated arrows | Done |

### Terrain (Phase C)

| Item | Status |
|------|--------|
| DEM import via Open-Meteo elevation API | Done — `make import-dem` |
| Cached grid `data/dem/{slug}.json` | Done |
| Slope / aspect / relative elevation at centroids | Done |
| Terrain subscore (`exposed_slope`, `lee_shelter`, `ridge_exposure`, `valley_channeling`) | Done |
| `terrain_class` ridge/valley/flat on slope zones | Done |

### Quality

- **64 backend tests** passing
- Frontend build in `make test`

---

## Not yet implemented

1. **BDNB / Grand Lyon 3D** — BD TOPO chosen as primary; alternatives not wired
2. **Deploy** to staging
3. **URock / vector-field generation** — zones marked scalar-limited only; animation hook ready
4. **Analytics export** (`make export-analytics`) — Phase 3 of current-state plan
5. **Pedestrian impact layer** — Phase 8 of current-state plan
6. **Dedicated About accuracy page** polish + feedback UI polish

---

## Known limitations

- Full Lyon `/exposure` GeoJSON is too large for live pan — use PMTiles map mode (default when tiles ready)
- Live scalar scoring blocked for Lyon (409) — intentional; prevents SQLite lock / timeout
- ~75 Presqu'île buildings still on `fallback_default` (BD TOPO centroid miss)
- ~8% Lyon buildings on fallback height
- Validation is manual sanity screening, not certified field truth
- Lyon DEM not applied until `make import-dem AREA=lyon_full` — hill scores use geometry until then
- Flow arrows on Lyon require `make generate-tiles` rerun to build `flow_*.pmtiles`
- Building exposure in tile mode can be heavy — off by default

---

## Milestone map

| Milestone | Topic | Status |
|-----------|-------|--------|
| M0–M5 | Scaffold, schema, scoring, pilot UI | **Done** |
| M6 | Real pilot data + quality dashboard | **Done** |
| M7 | Weather + gust overlay | **Done** |
| M8 | Full Lyon pipeline | **Done** — imported, enriched, audited |
| M9 | Directional precompute + PMTiles | **Done** — pilot + Lyon 16-dir |
| M11 | Validation harness | **Done** (pilot) |
| M10 | Vector zones + export | **Partial** — 3 zones; no URock |
| M12 | Public beta UX | **Partial** — Lyon map usable; about page light |

---

## Remaining phases (to v0.5 done)

Ordered by dependency — see [docs/plans/2026-07-01-v05-implementation-plan.md](docs/plans/2026-07-01-v05-implementation-plan.md).

### Phase A — Full Lyon data (M8) — done

- [x] 3×3 chunked Overpass import for `lyon_full`
- [x] `make pipeline` / `make pipeline-lyon` orchestrator + progress logs
- [x] Priority zone seeding (Vieux Lyon, hills, bridge corridors)
- [x] `make audit` city-wide quality report
- [x] Lyon full import run — 209k features, 91.8% official heights

### Phase B — Map performance (M9) — done

- [x] `make generate-tiles` — base + per-direction exposure PMTiles
- [x] API static serve `/tiles/{slug}/`
- [x] Frontend PMTiles protocol + vector layers when tiles ready
- [x] 16-direction precompute via `DIRECTIONS=16`
- [x] Building exposure layer toggle
- [x] Incremental tile swaps (direction / gust / confidence)
- [x] Large-area scalar guard (409)

**Tiles built:** `data/tiles/pilot_presquile/` (8 exposure + base), `data/tiles/lyon_full/` (16 exposure + base).

### Phase C — Terrain (M8 spike → metrics) — done

**Goal:** Real slope/ridge/valley modifiers for hills.

- [x] DEM import via Open-Meteo elevation API (`make import-dem`)
- [x] Slope/aspect/relative elevation sampled at feature centroids
- [x] Terrain subscore wired with `exposed_slope` / `lee_shelter` / `ridge_exposure` / `valley_channeling`
- [x] `terrain_class` on slope zones (ridge/valley/flat)

**Exit:** Hill areas score differently by wind direction after DEM import + optional `RECOMPUTE=1`.

### Phase C½ — Wind flow UI (vision plan) — done for v0.5 scalar mode

- [x] Backend `flow_indicators` service + `GET /areas/{slug}/flow`
- [x] Flow interpretation layer toggle + global wind compass
- [x] Corridor / bridge / quay / transition / model-limited markers
- [x] Explanation panel **Likely flow** section
- [x] Flow PMTiles generation (`flow_{direction}.pmtiles`)
- [x] Selected-feature arrow emphasis (dim unrelated)
- [x] Vector field animation hook (disabled until `vector_field_metadata` exists)

### Phase D — Vector zones polish (M10)

**Goal:** Honest scalar limits in complex districts.

- [ ] Expand `vector_zones` to plan list (Vieux Lyon/Saône transition, Croix-Rousse quay edge, bridge corridors)
- [ ] URock feasibility spike (optional — one zone test)
- [ ] Export package validation (buildings + wind scenario metadata)

**Exit:** Part-Dieu, Confluence, high-rise clusters show `vector_preferred` with export path.

### Phase E — Public beta UX (M12)

**Goal:** Shippable product surface.

- [x] Full Lyon default in area selector when imported
- [x] Layer selector — confidence, special geometry, gust, building exposure toggles
- [ ] Dedicated About accuracy page (limitations, confidence meaning, no-CFD claim)
- [ ] Feedback UI polish (location pick, wind context)
- [ ] Deploy staging (API + static frontend)

**Exit:** Non-technical user can explore Lyon, understand limits, report issues.

### Phase F — Validation expansion (post-pilot)

**Goal:** Stronger evidence, not certification.

- [ ] Grow sanity points toward 20–50 across priority zones
- [ ] Benchmark dataset spike (one loaded case if accessible)
- [ ] Re-run validation after full Lyon pipeline

**Exit:** Documented accuracy on expanded point set; baselines still beat flat wind.

---

## Suggested next command

```bash
make dev                    # explore Lyon map (PMTiles mode)
make validate               # pilot sanity check
make pipeline-lyon          # re-run only if forcing re-import
```