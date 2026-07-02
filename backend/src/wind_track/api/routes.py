"""API route handlers."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from wind_track.config.settings import settings
from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, loads_json, utc_now
from wind_track.models.schemas import (
    AreaResponse,
    DataQualityResponse,
    TileManifestResponse,
    FeatureResultResponse,
    FlowIndicatorResponse,
    FlowPathResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    ScalarScenarioRequest,
    ScenarioResponse,
    ValidationCaseResponse,
    ValidationMetricsResponse,
    ValidationRunRequest,
    WeatherResponse,
)
from wind_track.services.directional_cache import cache_status, get_cached_exposure
from wind_track.services.flow_indicators import get_flow_indicators
from wind_track.services.flow_paths import flow_paths_ready, get_flow_paths
from wind_track.services.tiles.generate import tile_manifest
from wind_track.services.precompute import precompute_directions
from wind_track.services.validation.run import run_validation_case, seed_presquile_validation_case
from wind_track.services.vector_export import export_vector_zone
from wind_track.services.scenarios import (
    get_feature_explanation,
    get_scenario_results,
    run_scalar_scenario,
)
from wind_track.services.weather.open_meteo import (
    cache_weather_for_area,
    get_current_weather,
    get_forecast,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.pipeline_version)


@router.get("/areas", response_model=list[AreaResponse])
async def list_areas() -> list[AreaResponse]:
    async with get_db() as conn:
        rows = await fetch_all(conn, "SELECT * FROM areas WHERE active = 1")
        return [
            AreaResponse(
                id=r["id"], slug=r["slug"], name=r["name"], area_type=r["area_type"],
                center_lat=r["center_lat"], center_lon=r["center_lon"],
                default_zoom=r["default_zoom"], active=bool(r["active"]),
            )
            for r in rows
        ]


@router.get("/areas/{area_id}/summary")
async def area_summary(area_id: int) -> dict[str, Any]:
    """Feature counts and data source for UI health checks."""
    async with get_db() as conn:
        counts = await fetch_all(
            conn,
            """SELECT feature_type, COUNT(*) as c FROM spatial_features
               WHERE area_id = ? GROUP BY feature_type""",
            (area_id,),
        )
        dv = await fetch_one(
            conn,
            "SELECT slug, summary_json FROM data_versions WHERE area_id = ? ORDER BY id DESC LIMIT 1",
            (area_id,),
        )
        source_type = "unknown"
        if dv:
            raw_ids = loads_json(dv.get("source_dataset_ids", "[]"), [])
            if raw_ids:
                sd = await fetch_one(
                    conn,
                    "SELECT source_type FROM source_datasets WHERE id = ?",
                    (raw_ids[0],),
                )
                if sd:
                    source_type = sd["source_type"]
        by_type = {row["feature_type"]: row["c"] for row in counts}
        streets = by_type.get("street_segment", 0)
        area_row = await fetch_one(conn, "SELECT slug FROM areas WHERE id = ?", (area_id,))
        slug = area_row["slug"] if area_row else ""
        cache = await cache_status(slug) if slug else {"ready": False}
        tiles = tile_manifest(slug) if slug else {"ready": False}
        paths_ready = await flow_paths_ready(slug) if slug else False
        return {
            "area_id": area_id,
            "feature_count": sum(by_type.values()),
            "street_count": streets,
            "feature_counts": by_type,
            "data_version": dv["slug"] if dv else None,
            "source_type": source_type,
            "needs_osm_import": streets < 50,
            "cache_ready": cache.get("ready", False),
            "cache_entries": cache.get("entry_count", 0),
            "tiles_ready": tiles.get("ready", False),
            "direction_count": cache.get("direction_count", 0),
            "flow_paths_ready": paths_ready,
        }


@router.get("/areas/{area_slug}/tiles", response_model=TileManifestResponse)
async def area_tiles(area_slug: str) -> TileManifestResponse:
    """PMTiles manifest for map performance layer."""
    manifest = tile_manifest(area_slug)
    return TileManifestResponse(area_slug=area_slug, **manifest)


@router.get("/areas/{area_slug}/exposure", response_model=list[FeatureResultResponse])
async def cached_exposure(
    area_slug: str,
    direction_deg: float = Query(..., ge=0, le=360),
    wind_speed_ms: float = Query(8.0, ge=0, le=40),
    wind_gust_ms: float | None = Query(None, ge=0, le=60),
    bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
) -> list[FeatureResultResponse]:
    """Fast exposure lookup from directional precompute cache."""
    direction_deg = direction_deg % 360
    parsed_bbox: tuple[float, float, float, float] | None = None
    if bbox:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) == 4:
            parsed_bbox = (parts[0], parts[1], parts[2], parts[3])
    results = await get_cached_exposure(
        area_slug, direction_deg, wind_speed_ms, wind_gust_ms, bbox=parsed_bbox,
    )
    if results is None:
        raise HTTPException(
            404,
            "Directional cache not ready — run: make precompute-directions",
        )
    return [FeatureResultResponse(**r) for r in results]


@router.get("/areas/{area_slug}/flow", response_model=list[FlowIndicatorResponse])
async def area_flow_indicators(
    area_slug: str,
    direction_deg: float = Query(..., ge=0, lt=360),
    wind_speed_ms: float = Query(8.0, ge=0, le=40),
    wind_gust_ms: float | None = Query(None, ge=0, le=60),
    bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
) -> list[FlowIndicatorResponse]:
    """Scalar flow interpretation indicators for map overlay."""
    parsed_bbox = None
    if bbox:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) == 4:
            parsed_bbox = (parts[0], parts[1], parts[2], parts[3])
    indicators = await get_flow_indicators(
        area_slug, direction_deg, wind_speed_ms, wind_gust_ms, parsed_bbox,
    )
    if not indicators:
        status = await cache_status(area_slug)
        if not status.get("ready"):
            raise HTTPException(
                404,
                "Directional cache not ready — run: make precompute-directions",
            )
    return [FlowIndicatorResponse(**ind) for ind in indicators]


@router.get("/areas/{area_slug}/flow-paths", response_model=list[FlowPathResponse])
async def area_flow_paths(
    area_slug: str,
    direction_deg: float = Query(..., ge=0, lt=360),
    wind_speed_ms: float = Query(8.0, ge=0, le=40),
    wind_gust_ms: float | None = Query(None, ge=0, le=60),
    bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
) -> list[FlowPathResponse]:
    """Normalized street flow paths with per-scenario meteor parameters."""
    parsed_bbox = None
    if bbox:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) == 4:
            parsed_bbox = (parts[0], parts[1], parts[2], parts[3])
    paths = await get_flow_paths(
        area_slug, direction_deg, wind_speed_ms, wind_gust_ms, parsed_bbox,
    )
    if not paths:
        if not await flow_paths_ready(area_slug):
            raise HTTPException(
                404,
                f"Flow paths not built for {area_slug} — run: "
                f"make build-flow-paths AREA={area_slug}",
            )
        status = await cache_status(area_slug)
        if not status.get("ready"):
            raise HTTPException(
                404,
                "Directional cache not ready — run: make precompute-directions",
            )
    return [FlowPathResponse(**row) for row in paths]


@router.get("/areas/{area_slug}/cache-status")
async def directional_cache_status(area_slug: str) -> dict[str, Any]:
    return await cache_status(area_slug)


@router.get("/areas/{area_id}", response_model=AreaResponse)
async def get_area(area_id: int) -> AreaResponse:
    async with get_db() as conn:
        row = await fetch_one(conn, "SELECT * FROM areas WHERE id = ?", (area_id,))
        if not row:
            raise HTTPException(404, "Area not found")
        return AreaResponse(
            id=row["id"], slug=row["slug"], name=row["name"], area_type=row["area_type"],
            center_lat=row["center_lat"], center_lon=row["center_lon"],
            default_zoom=row["default_zoom"], active=bool(row["active"]),
        )


@router.get("/areas/{area_id}/data-quality", response_model=DataQualityResponse)
async def data_quality(area_id: int) -> DataQualityResponse:
    async with get_db() as conn:
        buildings = await fetch_all(
            conn,
            "SELECT * FROM spatial_features WHERE area_id = ? AND feature_type = 'building'",
            (area_id,),
        )
        roads = await fetch_all(
            conn,
            """SELECT f.*, m.width_m FROM spatial_features f
               LEFT JOIN computed_feature_metrics m ON m.feature_id = f.id
               WHERE f.area_id = ? AND f.feature_type = 'street_segment'""",
            (area_id,),
        )
        special_types = [
            "bridge", "quay", "tunnel", "underpass", "high_rise_cluster",
            "irregular_fabric_zone", "slope_zone", "open_space",
        ]
        special_counts: dict[str, int] = {}
        for st in special_types:
            rows = await fetch_all(
                conn,
                "SELECT COUNT(*) as c FROM spatial_features WHERE area_id = ? AND feature_type = ?",
                (area_id, st),
            )
            special_counts[st] = rows[0]["c"] if rows else 0

        height_sources = [
            json.loads(b.get("properties_json") or "{}").get("height_source")
            for b in buildings
        ]
        official = sum(
            1 for hs in height_sources
            if hs in {"official", "osm_height", "official_file", "bdnb", "bdtopo"}
        )
        estimated = sum(
            1 for hs in height_sources
            if hs in {"osm_levels", "neighborhood_median"}
        )
        fallback = sum(
            1 for hs in height_sources
            if hs in {"synthetic", "fallback", "fallback_default", "fallback_street"}
        )
        low_conf = await fetch_one(
            conn,
            """SELECT COUNT(*) as c FROM computed_feature_metrics m
               JOIN spatial_features f ON f.id = m.feature_id
               WHERE f.area_id = ? AND m.handling_mode IN ('low_confidence', 'excluded')""",
            (area_id,),
        )
        veg = await fetch_one(
            conn,
            "SELECT COUNT(*) as c FROM spatial_features WHERE area_id = ? AND feature_type = 'vegetation'",
            (area_id,),
        )

        return DataQualityResponse(
            area_id=area_id,
            building_count=len(buildings),
            official_height_coverage=official / max(len(buildings), 1),
            estimated_height_coverage=estimated / max(len(buildings), 1),
            fallback_height_coverage=fallback / max(len(buildings), 1),
            missing_height_count=max(0, len(buildings) - official - estimated - fallback),
            roads_with_inferred_width=sum(1 for r in roads if r.get("width_m")),
            vegetation_count=veg["c"] if veg else 0,
            special_geometry_counts=special_counts,
            low_confidence_count=low_conf["c"] if low_conf else 0,
        )


@router.get("/areas/{area_id}/layers")
async def area_layers(area_id: int) -> dict[str, Any]:
    async with get_db() as conn:
        features = await fetch_all(
            conn,
            "SELECT id, feature_type, name, geom FROM spatial_features WHERE area_id = ?",
            (area_id,),
        )
        vector_zones = await fetch_all(
            conn,
            """SELECT vz.id, vz.name, vz.zone_type, vz.boundary_geom, vz.status,
                      EXISTS(
                        SELECT 1 FROM vector_field_metadata vfm
                        WHERE vfm.vector_zone_id = vz.id
                      ) AS vector_field_available
               FROM vector_zones vz WHERE vz.area_id = ?""",
            (area_id,),
        )
        return {
            "features": [
                {
                    "id": f["id"],
                    "feature_type": f["feature_type"],
                    "name": f["name"],
                    "geom": json.loads(f["geom"]),
                }
                for f in features
            ],
            "vector_zones": [
                {
                    "id": vz["id"],
                    "name": vz["name"],
                    "zone_type": vz["zone_type"],
                    "status": vz["status"],
                    "vector_field_available": bool(vz.get("vector_field_available")),
                    "boundary": json.loads(vz["boundary_geom"]),
                }
                for vz in vector_zones
            ],
        }


@router.get("/features")
async def list_features(
    area_id: int = Query(...),
    bbox: str | None = Query(None, description="min_lon,min_lat,max_lon,max_lat"),
    feature_type: str | None = None,
) -> list[dict[str, Any]]:
    async with get_db() as conn:
        query = "SELECT f.* FROM spatial_features f"
        params: list[Any] = [area_id]
        clauses = ["f.area_id = ?"]

        if bbox:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                query += " JOIN spatial_features_rtree idx ON idx.id = f.id"
                clauses += [
                    "idx.max_x >= ?", "idx.min_x <= ?",
                    "idx.max_y >= ?", "idx.min_y <= ?",
                ]
                params.extend(parts)

        if feature_type:
            clauses.append("f.feature_type = ?")
            params.append(feature_type)

        query += " WHERE " + " AND ".join(clauses)
        rows = await fetch_all(conn, query, tuple(params))
        return [
            {
                "id": r["id"],
                "feature_type": r["feature_type"],
                "name": r["name"],
                "geom": json.loads(r["geom"]),
                "properties": loads_json(r.get("properties_json"), {}),
            }
            for r in rows
        ]


@router.get("/features/{feature_id}/explanation")
async def feature_explanation(
    feature_id: int,
    scenario_id: int = Query(...),
) -> FeatureResultResponse:
    result = await get_feature_explanation(feature_id, scenario_id)
    if not result:
        raise HTTPException(404, "Explanation not found")
    return FeatureResultResponse(**result)


LARGE_AREA_FEATURE_LIMIT = 10_000


@router.post("/scenarios/scalar", response_model=ScenarioResponse)
async def create_scalar_scenario(body: ScalarScenarioRequest) -> ScenarioResponse:
    cache = await cache_status(body.area_slug)
    if cache.get("ready"):
        async with get_db() as conn:
            area = await fetch_one(conn, "SELECT id FROM areas WHERE slug = ?", (body.area_slug,))
            if area:
                row = await fetch_one(
                    conn,
                    "SELECT COUNT(*) as c FROM spatial_features WHERE area_id = ?",
                    (area["id"],),
                )
                if row and row["c"] > LARGE_AREA_FEATURE_LIMIT:
                    raise HTTPException(
                        409,
                        "Area too large for live scoring — use GET /areas/{slug}/exposure "
                        "or PMTiles map mode",
                    )
    result = await run_scalar_scenario(
        body.area_slug,
        body.wind_speed_ms,
        body.wind_direction_deg,
        body.scenario_type,
        body.weather_observation_id,
        body.wind_gust_ms,
    )
    return ScenarioResponse(**result)


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: int) -> dict[str, Any]:
    async with get_db() as conn:
        row = await fetch_one(conn, "SELECT * FROM scenario_runs WHERE id = ?", (scenario_id,))
        if not row:
            raise HTTPException(404, "Scenario not found")
        return dict(row)


@router.get("/scenarios/{scenario_id}/results", response_model=list[FeatureResultResponse])
async def scenario_results(
    scenario_id: int,
    bbox: str | None = Query(None),
) -> list[FeatureResultResponse]:
    bbox_tuple = None
    if bbox:
        parts = [float(x) for x in bbox.split(",")]
        if len(parts) == 4:
            bbox_tuple = (parts[0], parts[1], parts[2], parts[3])
    results = await get_scenario_results(scenario_id, bbox_tuple)
    return [FeatureResultResponse(**r) for r in results]


@router.get("/weather/current", response_model=WeatherResponse)
async def weather_current(area_id: int = Query(...)) -> WeatherResponse:
    row = await get_current_weather(area_id)
    if not row:
        raise HTTPException(404, "No weather data — try POST /weather/refresh")
    return WeatherResponse(
        area_id=row["area_id"],
        wind_speed_10m_ms=row.get("wind_speed_10m_ms"),
        wind_direction_10m_deg=row.get("wind_direction_10m_deg"),
        wind_gust_10m_ms=row.get("wind_gust_10m_ms"),
        timestamp=row["timestamp"],
        source=row["source"],
    )


@router.get("/weather/forecast", response_model=list[WeatherResponse])
async def weather_forecast(area_id: int = Query(...)) -> list[WeatherResponse]:
    rows = await get_forecast(area_id)
    return [
        WeatherResponse(
            area_id=r["area_id"],
            wind_speed_10m_ms=r.get("wind_speed_10m_ms"),
            wind_direction_10m_deg=r.get("wind_direction_10m_deg"),
            wind_gust_10m_ms=r.get("wind_gust_10m_ms"),
            timestamp=r["timestamp"],
            source=r["source"],
            is_forecast=True,
            forecast_timestamp=r.get("forecast_timestamp"),
        )
        for r in rows
    ]


@router.post("/weather/refresh")
async def weather_refresh(area_id: int = Query(...)) -> dict[str, Any]:
    async with get_db() as conn:
        area = await fetch_one(conn, "SELECT * FROM areas WHERE id = ?", (area_id,))
        if not area:
            raise HTTPException(404, "Area not found")
        ids = await cache_weather_for_area(area_id, area["center_lat"], area["center_lon"])
        return {"cached_count": len(ids), "observation_ids": ids}


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(body: FeedbackRequest) -> FeedbackResponse:
    async with get_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO user_feedback
               (area_id, feature_id, feedback_type, description, wind_direction_deg,
                weather_context_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?)""",
            (
                body.area_id, body.feature_id, body.feedback_type, body.description,
                body.wind_direction_deg, dumps_json(body.weather_context), utc_now(),
            ),
        )
        return FeedbackResponse(id=cursor.lastrowid or 0, status="new")


@router.get("/feedback")
async def list_feedback(
    area_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    async with get_db() as conn:
        query = "SELECT * FROM user_feedback WHERE 1=1"
        params: list[Any] = []
        if area_id:
            query += " AND area_id = ?"
            params.append(area_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        rows = await fetch_all(conn, query, tuple(params))
        return [dict(r) for r in rows]


@router.get("/validation/cases", response_model=list[ValidationCaseResponse])
async def list_validation_cases(area_id: int | None = None) -> list[ValidationCaseResponse]:
    async with get_db() as conn:
        query = "SELECT c.*, COUNT(s.id) as sample_count FROM validation_cases c"
        query += " LEFT JOIN validation_samples s ON s.validation_case_id = c.id"
        params: list[Any] = []
        if area_id:
            query += " WHERE c.area_id = ?"
            params.append(area_id)
        query += " GROUP BY c.id ORDER BY c.id"
        rows = await fetch_all(conn, query, tuple(params))
        return [
            ValidationCaseResponse(
                id=r["id"],
                name=r["name"],
                case_type=r["case_type"],
                area_id=r["area_id"],
                wind_direction_deg=r.get("wind_direction_deg"),
                reference_speed_ms=r.get("reference_speed_ms"),
                sample_count=r.get("sample_count", 0),
            )
            for r in rows
        ]


@router.post("/validation/seed")
async def seed_validation(area_slug: str = Query(default="pilot_presquile")) -> dict[str, Any]:
    return await seed_presquile_validation_case(area_slug)


@router.post("/validation/run", response_model=ValidationMetricsResponse)
async def run_validation(body: ValidationRunRequest) -> ValidationMetricsResponse:
    result = await run_validation_case(body.validation_case_id, body.model_version_id)
    metrics = result["metrics"]
    return ValidationMetricsResponse(
        validation_case_id=body.validation_case_id,
        overall_accuracy=metrics["overall_accuracy"],
        high_wind_recall=metrics.get("high_wind_recall"),
        high_wind_precision=metrics.get("high_wind_precision"),
        adjacent_class_accuracy=metrics["adjacent_class_accuracy"],
        false_negative_rate=metrics.get("false_negative_rate"),
        metrics_json=metrics,
    )


@router.get("/validation/metrics")
async def get_validation_metrics(
    validation_case_id: int = Query(...),
) -> list[dict[str, Any]]:
    async with get_db() as conn:
        rows = await fetch_all(
            conn,
            """SELECT vm.*, mv.slug as model_slug FROM validation_metrics vm
               JOIN model_versions mv ON mv.id = vm.model_version_id
               WHERE vm.validation_case_id = ?
               ORDER BY vm.id DESC LIMIT 10""",
            (validation_case_id,),
        )
        return [
            {
                **dict(r),
                "metrics_json": loads_json(r.get("metrics_json"), {}),
            }
            for r in rows
        ]


@router.get("/areas/{area_id}/vector-zones/{zone_id}/export")
async def vector_zone_export(area_id: int, zone_id: int) -> dict[str, Any]:
    return await export_vector_zone(area_id, zone_id)


@router.post("/admin/precompute")
async def admin_precompute(
    area_slug: str = Query(default="pilot_presquile"),
    directions: str = Query(default="0,45,90,135,180,225,270,315"),
) -> dict[str, int]:
    dirs = [int(d) for d in directions.split(",")]
    return await precompute_directions(area_slug, dirs)