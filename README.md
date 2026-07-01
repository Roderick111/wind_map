# Wind Track

Urban wind exposure screening for Lyon. Estimates street-level exposure from regional wind and urban geometry — not CFD.

## Quick start

```bash
make db-migrate
make import-osm    # real Presqu'île OSM data (recommended)
make dev
```

For synthetic test data only: `make seed`

- API: http://localhost:8002/health
- Map: http://localhost:5181

## Commands

| Command | Description |
|---------|-------------|
| `make dev` | Backend (8002) + frontend (5181) |
| `make test` | pytest + frontend build |
| `make db-migrate` | Apply SQLite schema |
| `make seed` | Load synthetic test data (dev/tests) |
| `make import-osm` | Import real Presqu'île OSM streets, rivers, buildings |
| `make precompute-directions` | Cache 8-direction scalar scores |

## Stack

- **Backend:** Python FastAPI, SQLite, Shapely
- **Frontend:** Vite React, MapLibre GL JS, TanStack Query, Zod

## Product claim

> Street-level wind exposure estimated from regional forecast wind and urban geometry.

Not engineering-grade wind speed, certified pedestrian comfort, or real-time CFD.