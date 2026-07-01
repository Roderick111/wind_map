"""Validation case execution."""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import Point, shape

from wind_track.db.connection import dumps_json, fetch_all, fetch_one, get_db, loads_json, utc_now
from wind_track.services.geo import geom_from_geojson
from wind_track.services.scenarios import get_active_versions
from wind_track.services.scoring.config import DEFAULT_SCALAR_CONFIG
from wind_track.services.validation.baselines import BASELINE_SCORERS
from wind_track.services.validation.metrics import compute_validation_metrics
from wind_track.services.validation.samples import PRESQUILE_SANITY_SAMPLES


def _metrics_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "orientation_deg": row.get("orientation_deg"),
        "corridor_orientation_deg": row.get("corridor_orientation_deg"),
        "width_m": row.get("width_m"),
        "height_m": row.get("height_m"),
        "hw_ratio": row.get("hw_ratio"),
        "curvature_score": row.get("curvature_score"),
        "enclosure_ratio": row.get("enclosure_ratio"),
        "river_distance_m": row.get("river_distance_m"),
        "river_axis_deg": row.get("river_axis_deg"),
        "vegetation_density": row.get("vegetation_density"),
        "slope_deg": row.get("slope_deg"),
        "slope_aspect_deg": row.get("slope_aspect_deg"),
        "nearby_highrise_score": row.get("nearby_highrise_score"),
        "special_geometry_type": row.get("special_geometry_type"),
        "handling_mode": row.get("handling_mode"),
        "metric_confidence": row.get("metric_confidence"),
    }


def _find_nearest_feature(
    features: list[dict[str, Any]],
    lon: float,
    lat: float,
    preferred_types: list[str] | None,
    max_m: float = 120.0,
) -> dict[str, Any] | None:
    """Match sample point to nearest feature (approximate degrees → metres)."""
    pt = Point(lon, lat)
    best: dict[str, Any] | None = None
    best_dist = max_m / 111_000
    for feat in features:
        if preferred_types and feat["feature_type"] not in preferred_types:
            continue
        try:
            g = geom_from_geojson(feat["geom"])
            d = pt.distance(g.centroid)
        except Exception:
            continue
        if d < best_dist:
            best_dist = d
            best = feat
    if best:
        return best
    for feat in features:
        try:
            g = geom_from_geojson(feat["geom"])
            d = pt.distance(g.centroid)
        except Exception:
            continue
        if d < best_dist:
            best_dist = d
            best = feat
    return best


async def seed_presquile_validation_case(area_slug: str = "pilot_presquile") -> dict[str, Any]:
    """Create or refresh Presqu'île manual sanity validation case."""
    versions = await get_active_versions(area_slug)
    if not versions or not versions["area"]:
        raise ValueError(f"Area not found: {area_slug}")

    area = versions["area"]
    now = utc_now()
    async with get_db() as conn:
        existing = await fetch_one(
            conn,
            """SELECT id FROM validation_cases
               WHERE area_id = ? AND case_type = 'manual_sanity'""",
            (area["id"],),
        )
        if existing:
            case_id = existing["id"]
            await conn.execute(
                "DELETE FROM validation_samples WHERE validation_case_id = ?",
                (case_id,),
            )
            await conn.execute(
                "DELETE FROM validation_metrics WHERE validation_case_id = ?",
                (case_id,),
            )
        else:
            cursor = await conn.execute(
                """INSERT INTO validation_cases
                   (name, case_type, area_id, wind_direction_deg, reference_speed_ms, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "Presqu'île sanity checklist",
                    "manual_sanity",
                    area["id"],
                    None,
                    8.0,
                    dumps_json({"source": "manual", "sample_count": len(PRESQUILE_SANITY_SAMPLES)}),
                ),
            )
            case_id = cursor.lastrowid

        features = await fetch_all(
            conn,
            "SELECT id, feature_type, name, geom FROM spatial_features WHERE area_id = ?",
            (area["id"],),
        )
        inserted = 0
        for sample in PRESQUILE_SANITY_SAMPLES:
            feat = _find_nearest_feature(
                features,
                sample["lon"],
                sample["lat"],
                sample.get("feature_types"),
            )
            geom = json.dumps({
                "type": "Point",
                "coordinates": [sample["lon"], sample["lat"]],
            })
            await conn.execute(
                """INSERT INTO validation_samples
                   (validation_case_id, feature_id, geom, observed_class, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    case_id,
                    feat["id"] if feat else None,
                    geom,
                    sample["observed_class"],
                    sample.get("notes", sample["name"]),
                ),
            )
            inserted += 1

    return {"validation_case_id": case_id, "samples_seeded": inserted}


async def run_validation_case(
    case_id: int,
    model_version_id: int | None = None,
) -> dict[str, Any]:
    """Score validation samples with baselines and store metrics."""
    async with get_db() as conn:
        case = await fetch_one(conn, "SELECT * FROM validation_cases WHERE id = ?", (case_id,))
        if not case:
            raise ValueError(f"Validation case {case_id} not found")

        area_row = await fetch_one(
            conn, "SELECT slug FROM areas WHERE id = ?", (case["area_id"],),
        )
        if not area_row:
            raise ValueError("Validation case area missing")
        versions = await get_active_versions(area_row["slug"])
        if not versions or not versions["data_version"] or not versions["model_version"]:
            raise ValueError("No active data/model version for validation area")

        data_version = versions["data_version"]
        model_version = versions["model_version"]
        if model_version_id:
            mv = await fetch_one(conn, "SELECT * FROM model_versions WHERE id = ?", (model_version_id,))
            if mv:
                model_version = mv

        config = loads_json(model_version["config_json"], DEFAULT_SCALAR_CONFIG)
        samples = await fetch_all(
            conn,
            "SELECT * FROM validation_samples WHERE validation_case_id = ? ORDER BY id",
            (case_id,),
        )
        feature_rows = await fetch_all(
            conn,
            """SELECT f.*, m.* FROM spatial_features f
               JOIN computed_feature_metrics m ON m.feature_id = f.id
               WHERE f.area_id = ? AND m.data_version_id = ?""",
            (case["area_id"], data_version["id"]),
        )
        by_id = {r["id"]: r for r in feature_rows}

        ref_speed = case["reference_speed_ms"] or 8.0
        scored: list[dict[str, Any]] = []

        for idx, sample in enumerate(samples):
            wind_deg = (
                PRESQUILE_SANITY_SAMPLES[idx]["wind_direction_deg"]
                if idx < len(PRESQUILE_SANITY_SAMPLES)
                else (case["wind_direction_deg"] or 90)
            )
            feat = by_id.get(sample["feature_id"]) if sample.get("feature_id") else None
            if not feat:
                geom = loads_json(sample.get("geom"), {})
                coords = geom.get("coordinates", [4.835, 45.764])
                feat = _find_nearest_feature(feature_rows, coords[0], coords[1], None)
            if not feat:
                continue

            metrics = _metrics_from_row(feat)
            ftype = feat["feature_type"]
            flat = BASELINE_SCORERS["flat_wind"](ftype, metrics, wind_deg, ref_speed, config)
            align = BASELINE_SCORERS["alignment_only"](ftype, metrics, wind_deg, ref_speed, config)
            density = BASELINE_SCORERS["density_only"](ftype, metrics, wind_deg, ref_speed, config)
            full = BASELINE_SCORERS["full_scalar"](ftype, metrics, wind_deg, ref_speed, config)

            row_data = {
                "sample_id": sample["id"],
                "feature_id": feat["id"],
                "observed_class": sample["observed_class"],
                "predicted_flat": flat["exposure_class"],
                "predicted_alignment": align["exposure_class"],
                "predicted_density": density["exposure_class"],
                "predicted_full": full["exposure_class"],
                "predicted_score": full["risk_score"],
                "confidence": full.get("confidence"),
            }
            scored.append(row_data)

            await conn.execute(
                """UPDATE validation_samples SET
                   predicted_class = ?, predicted_score = ?, confidence = ?
                   WHERE id = ?""",
                (full["exposure_class"], full["risk_score"], full.get("confidence"), sample["id"]),
            )

        metrics = compute_validation_metrics(scored)
        await conn.execute(
            """INSERT INTO validation_metrics
               (validation_case_id, model_version_id, data_version_id,
                overall_accuracy, high_wind_recall, high_wind_precision,
                adjacent_class_accuracy, false_negative_rate, metrics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                case_id,
                model_version["id"],
                data_version["id"],
                metrics["overall_accuracy"],
                metrics.get("high_wind_recall"),
                metrics.get("high_wind_precision"),
                metrics["adjacent_class_accuracy"],
                metrics.get("false_negative_rate"),
                dumps_json(metrics),
            ),
        )

    return {"case_id": case_id, "samples_scored": len(scored), "metrics": metrics}