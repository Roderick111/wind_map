# AGENTS.md

Dev guide for **Wind Track** — urban wind exposure map for Lyon. Architecture details in [README.md](README.md) and [docs/plans/](docs/plans/).

## Project values

- **Flexible & reliable** — handle varied wind scenarios and geometry types without failing silently
- **Elegant & logical** — YAGNI; no duplicate abstractions; scoring logic must be explainable
- **Performance** — heavy geospatial work in batch jobs; map layers via precomputed tiles/cache, not live SQL per pan

Be sceptical of blind deterministic rules. Scalar heuristics are fine when decomposed into sub-scores, cause tags, confidence, and handling modes — not when they hide uncertainty.

## Product positioning

Correct claim:

> Street-level wind exposure estimated from regional forecast wind and urban geometry.

Never claim: engineering-grade wind speed, certified pedestrian comfort, real-time CFD, or exact turbulent airflow.

Low confidence reduces certainty, not displayed risk.

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.13, FastAPI, Pydantic v2, aiosqlite, Shapely |
| Frontend | Bun, Vite, React, MapLibre GL JS, Zod, TanStack Query |
| Database | SQLite (`data/wind_track.db`) — product store, versioned |
| Weather | Open-Meteo (reference wind at 10 m, not street truth) |

**Not used here:** Hono, Postgres, BHVR. Those belong to other projects.

## Ports

| Service | Port |
|---------|------|
| Backend API | **8002** |
| Frontend dev | **5181** |

CORS defaults live in `backend/src/wind_track/config/settings.py`, not `.env`.

## Run & validate

```bash
make db-migrate && make import-osm
make dev          # backend 8002 + frontend 5181

make test         # pytest + frontend build
```

Manual:

```bash
cd backend && uv run uvicorn wind_track.main:app --reload --port 8002
cd frontend && ~/.bun/bin/bun run dev
```

```bash
cd backend && uv run ruff check src/ tests/ && uv run pytest -v
cd frontend && ~/.bun/bin/bun run build
```

## Tooling rules

### Bun (frontend only)

- ALWAYS `bun`, NEVER `npm`/`yarn`/`pnpm`
- Use full path when needed: `~/.bun/bin/bun run dev`
- `bun add <pkg>` / `bun add -d <pkg>`

### UV (backend)

- NEVER edit `pyproject.toml` deps by hand — use `uv add` / `uv add --dev`
- `uv run <cmd>` for all Python execution
- Migrations run via `make db-migrate` or `uv run wind-track-migrate`

### SQL

- Never execute ad-hoc SQL in agent shell. Schema changes go in `backend/src/wind_track/db/schema.sql` + migration runner.

### Git

- Ask before pushing
- Primary GitHub interaction: `gh` CLI
- Commits: `<type>(<scope>): <subject>` — never mention Claude Code

## Key paths

```
backend/src/wind_track/
  main.py              # FastAPI app
  config/settings.py   # ports, CORS, DB path
  db/schema.sql        # SQLite schema
  services/scoring/    # scalar model
  services/seed.py     # synthetic pilot data
  api/routes.py        # REST endpoints

frontend/src/
  api/schemas.ts       # Zod — must match Pydantic models
  api/client.ts        # API client
  components/          # MapView, WindControls, ExplanationPanel

data/wind_track.db     # created by migrate + seed
```

## API ↔ frontend contract

When adding/changing endpoints:

1. Pydantic model in `backend/src/wind_track/models/schemas.py`
2. Route in `backend/src/wind_track/api/routes.py`
3. Zod schema in `frontend/src/api/schemas.ts` — match all fields, `.optional()` for nullable, keep `.strict()`

## Data pipeline

```bash
make import-osm                          # real Presqu'île OSM (streets, rivers, buildings)
make seed                              # synthetic data for tests only
make precompute-directions AREA=pilot_presquile
```

Planned (not all implemented): `import-osm`, `compute-metrics`, `generate-tiles` for full Lyon.

## Architecture decisions

- **SQLite center** — spatial features, metrics, scenarios, scalar results, directional cache
- **`spatial_features` not `streets`** — typed feature classes (bridge, quay, tunnel, etc.)
- **Handling modes** — `normal_score`, `special_rule`, `low_confidence`, `excluded`, `vector_preferred`
- **Model versioning** — thresholds and multipliers in `model_versions.config_json`, not hardcoded in UI
- **Map serving** — GeoJSON for pilot; PMTiles for full Lyon later
- **Vite proxy** — frontend `/api` → `http://127.0.0.1:8002`

## Code limits

| Unit | Max lines |
|------|-----------|
| File | 500 |
| Function | 50 |
| Class | 100 |
| Line length | 100 (Ruff) |

## Style

- PEP8, type hints, double quotes, trailing commas in multi-line structures
- Google-style docstrings for public APIs
- `snake_case` / `PascalCase` / `UPPER_SNAKE_CASE`

## Plans

At end of each plan: list unresolved questions for the user.

## YAGNI

1. Need exist? → skip
2. Stdlib? → use it
3. Existing dep? → use it
4. One line works? → one line
5. Else → minimum that works

## Agent orchestration

Orchestrator reads docs, injects context into subagents, validates with tests.

| Change | Pipeline |
|--------|----------|
| Bug fix | Direct fix + test |
| Small feature | Implement → ruff/pytest/build |
| Full-stack | Backend + frontend schema sync → integration test |

## Critical rules

1. Verify file paths before use
2. No feature done without tests where applicable
3. `uv add` / `bun add` for deps — no hand-editing lockfiles
4. Run `ruff`, `pytest`, `bun build` before commit
5. Don't change ports/API keys/model defaults without user ask — unless user reports port conflict

## Caveman mode

Respond terse like smart caveman. Technical substance stays. Off only on: "stop caveman" / "normal mode", security warnings, irreversible confirmations.

Code/commits/PRs: write normal prose.