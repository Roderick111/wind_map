.PHONY: dev test setup db-migrate seed import-osm enrich-heights validate compute-metrics precompute-directions generate-tiles audit pipeline backend frontend

# One-time (or after schema change): migrate + import OSM if missing
setup:
	$(MAKE) db-migrate
	$(MAKE) import-osm

dev:
	$(MAKE) -j2 backend frontend

backend:
	cd backend && uv run uvicorn wind_track.main:app --reload --port 8002

frontend:
	cd frontend && ~/.bun/bin/bun run dev --port 5181

test:
	cd backend && uv run pytest -v
	cd frontend && ~/.bun/bin/bun run build

db-migrate:
	cd backend && uv run wind-track-migrate

seed:
	cd backend && uv run wind-track-seed

import-osm:
	cd backend && uv run wind-track-import-osm $(or $(AREA),pilot_presquile) $(if $(FORCE),--force,)

compute-metrics:
	cd backend && uv run wind-track-metrics $(or $(AREA),pilot_presquile)

precompute-directions:
	cd backend && uv run wind-track-precompute $(or $(AREA),pilot_presquile) --directions $(or $(DIRECTIONS),8)

enrich-heights:
	cd backend && uv run wind-track-enrich-heights $(or $(AREA),pilot_presquile)

validate:
	cd backend && uv run wind-track-validate $(or $(AREA),pilot_presquile)

audit:
	cd backend && uv run wind-track-audit $(or $(AREA),pilot_presquile)

generate-tiles:
	cd backend && uv run wind-track-generate-tiles $(or $(AREA),pilot_presquile) --directions $(or $(DIRECTIONS),8)

# Full Lyon pipeline: import (3×3 Overpass grid) → enrich → zones → precompute → tiles → audit
pipeline-lyon:
	$(MAKE) pipeline AREA=lyon_full DIRECTIONS=$(or $(DIRECTIONS),16)

pipeline:
	cd backend && PYTHONUNBUFFERED=1 uv run wind-track-pipeline $(or $(AREA),pilot_presquile) --directions $(or $(DIRECTIONS),8) $(if $(FORCE),--force,) $(if $(SKIP_TILES),--skip-tiles,)