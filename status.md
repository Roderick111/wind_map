# Wind Track — implementation status

Last updated: 2026-07-01

**Scope:** v0.5 beta — Presqu'île pilot + Lyon full (import-ready). Screening tool, not CFD.

## Running locally

```bash
make setup          # migrate + import OSM if missing
make dev            # API :8002, map :5181
make test           # isolated test DB — dev data safe

make enrich-heights # BD TOPO + neighborhood median + quay promotion
make validate       # seed + run Presqu'île sanity validation
make import-osm AREA=lyon_full FORCE=1   # full city (slow; Overpass)
```

Dev data persists in `data/wind_track.db`.

---

## Implemented

### Data & pipeline

| Item | Status |
|------|--------|
| SQLite schema + migrations | Done |
| Presqu'île OSM import | Done — ~7k features |
| **Lyon full area** (`lyon_full`) | Done — bbox + import CLI (not pre-imported) |
| Import skip-if-present + `FORCE=1` | Done |
| Metrics batch | Done |
| 8-direction precompute cache | Done |
| **BD TOPO height enrichment** | Done — IGN WFS `BDTOPO_V3:batiment`, centroid match |
| **Quay detection** | Done — `Quai …` name + `man_made` tags at import; `promote_quay_streets()` on import/enrich |
| Neighborhood height fallback | Done — 40 m OSM median for unmatched buildings |
| Optional file patches | Done — `data/heights/{slug}.geojson` |
| PMTiles | Not started |

**Presqu'île data quality (after enrich):**

| Metric | Value |
|--------|-------|
| Buildings | ~2 624 |
| Official height (`bdtopo` + `osm_height`) | **~96.5%** |
| Estimated height (`osm_levels`, `neighborhood_median`) | ~0.7% |
| Fallback (`fallback_default`) | ~2.9% |
| Quays | **129** (was 0) |

### Scoring (scalar v0.1)

- Full subscore model + special rules + handling modes
- **Weather gust boost** — Open-Meteo gust/speed ratio raises risk + `gust_sensitive` flag
- Gust wired through cache path (`wind_gust_ms` query param)

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
| `GET /areas/{id}/data-quality` | Official / estimated / fallback height tiers |
| `POST /validation/seed` | Seed sanity case |
| `POST /validation/run` | Run baselines + metrics |
| `GET /areas/{id}/vector-zones/{id}/export` | Vector research package |
| `POST /feedback` | User issue reports |

### Frontend

| Feature | Status |
|---------|--------|
| Manual / current / forecast + instant cache | Done |
| **Gust layer** — geometry + forecast gusts | Done |
| **Validation panel** | Done |
| **Area selector** (when multiple areas in DB) | Done |
| **Data quality panel** — official / estimated / fallback tiers | Done |
| Explanation + vector disclaimer | Done |
| About accuracy section | Partial — inline in app, not dedicated page |
| Feedback button | Partial — API wired, minimal UI |

### Quality

- **47 backend tests** passing
- Frontend build in `make test`

---

## Not yet implemented

1. **Full Lyon OSM import** — area defined; import not run (Overpass scale/timeout risk)
2. **PMTiles** — city-wide performant layers (required before smooth full-Lyon pan)
3. **DEM / terrain** — Fourvière, Croix-Rousse slope metrics still placeholders
4. **BDNB / Grand Lyon 3D** — BD TOPO chosen as primary; alternatives not wired
5. **16-direction precompute** — 8-dir done; 16 optional per plan
6. **Deploy** to staging
7. **URock / vector-field generation** — zones marked scalar-limited only

---

## Known limitations

- Full Lyon OSM import is large — Overpass may timeout; use retries or off-peak
- ~75 Presqu'île buildings still on `fallback_default` (BD TOPO centroid miss)
- Validation is manual sanity screening, not certified field truth
- Each `/exposure` returns full area GeoJSON (~7k features for pilot)
- PMTiles required before smooth full-Lyon pan/zoom at scale
- Hills/slopes scored without real DEM — terrain subscore is weak

---

## Milestone map

| Milestone | Topic | Status |
|-----------|-------|--------|
| M0–M5 | Scaffold, schema, scoring, pilot UI | **Done** |
| M6 | Real pilot data + quality dashboard | **Done** (BD TOPO + quays closed gaps) |
| M7 | Weather + gust overlay | **Done** |
| M9 | Directional precompute | **Done** (pilot); tiles pending |
| M11 | Validation harness | **Done** (pilot) |
| M10 | Vector zones + export | **Partial** — 3 zones; no URock |
| M8 | Full Lyon pipeline | **Partial** — area + import CLI; no full import/DEM |
| M12 | Public beta UX | **Partial** — pilot polished; full Lyon + about page light |

---

## Remaining phases (to v0.5 done)

Ordered by dependency — see [docs/plans/2026-07-01-v05-implementation-plan.md](docs/plans/2026-07-01-v05-implementation-plan.md).

### Phase A — Full Lyon data (M8)

**Goal:** Reproducible city-wide static layers.

- [ ] Run `make import-osm AREA=lyon_full` (may need chunked bbox or off-peak)
- [ ] `make enrich-heights AREA=lyon_full` (BD TOPO paginated fetch)
- [ ] `make precompute-directions AREA=lyon_full`
- [ ] City-wide data quality audit (same tiers as pilot)
- [ ] Priority zone detection: Vieux Lyon fabric, Fourvière/Croix-Rousse slopes, all major bridges

**Exit:** Full Lyon explorable with honest quality report; weak areas flagged.

### Phase B — Map performance (M9 tiles)

**Goal:** Fast pan/zoom at city scale.

- [ ] `make generate-tiles` — PMTiles for exposure + base geometry layers
- [ ] Serve tiles from API or static CDN path
- [ ] Frontend: PMTiles source instead of full GeoJSON per pan
- [ ] Optional: 16-direction precompute if 8-dir interpolation is too coarse

**Exit:** Direction switch &lt;1 s; layer load &lt;5 s for full Lyon viewport.

### Phase C — Terrain (M8 spike → metrics)

**Goal:** Real slope/ridge/valley modifiers for hills.

- [ ] DEM import spike (IGN/RGE ALTI or equivalent)
- [ ] `slope_zone` / `ridge_zone` generation for Fourvière, Croix-Rousse
- [ ] Wire terrain subscore (currently placeholder)

**Exit:** Hill/quay transition areas score differently with `exposed_slope` / `lee_shelter` tags.

### Phase D — Vector zones polish (M10)

**Goal:** Honest scalar limits in complex districts.

- [ ] Expand `vector_zones` to plan list (Vieux Lyon/Saône transition, Croix-Rousse quay edge, bridge corridors)
- [ ] URock feasibility spike (optional — one zone test)
- [ ] Export package validation (buildings + wind scenario metadata)

**Exit:** Part-Dieu, Confluence, high-rise clusters show `vector_preferred` with export path.

### Phase E — Public beta UX (M12)

**Goal:** Shippable product surface.

- [ ] Full Lyon default in area selector when imported
- [ ] Dedicated About accuracy page (limitations, confidence meaning, no-CFD claim)
- [ ] Feedback UI polish (location pick, wind context)
- [ ] Layer selector cleanup (confidence, special geometry, gust toggles)
- [ ] Deploy staging (API + static frontend)

**Exit:** Non-technical user can explore Lyon, understand limits, report issues.

### Phase F — Validation expansion (post-pilot)

**Goal:** Stronger evidence, not certification.

- [ ] Grow sanity points toward 20–50 across priority zones
- [ ] Benchmark dataset spike (one loaded case if accessible)
- [ ] Re-run validation after M8/M9 pipeline on full Lyon

**Exit:** Documented accuracy on expanded point set; baselines still beat flat wind.

---

## Suggested next command

```bash
make enrich-heights AREA=pilot_presquile   # already run — re-run after re-import
make import-osm AREA=lyon_full FORCE=1   # Phase A start (long; network)
```