"""Lightweight graph-based street-flow simulation for meteor animation."""

from __future__ import annotations

from dataclasses import dataclass

from wind_track.services.geo import alignment_score, angle_diff_deg

MIN_CONFIDENCE = 0.35
MIN_ENERGY = 0.06
RELAX_PASSES = 3
TURN_SOFT_DEG = 55.0
TURN_HARD_DEG = 95.0


@dataclass
class PathRow:
    """DB/API flow path with geometry metadata."""

    flow_path_id: int
    source_feature_ids: list[int]
    path_type: str
    name: str | None
    geom: dict
    length_m: float
    bearing_deg: float
    from_node_id: int | None
    to_node_id: int | None
    confidence: float


@dataclass
class SimulatedFlow:
    """Per-path animation parameters."""

    flow_path_id: int
    flow_direction_deg: float
    flow_strength: float
    meteor_density: float
    confidence: float
    animate: bool
    reason: str


def _blow_direction_deg(wind_from_deg: float) -> float:
    return (wind_from_deg + 180) % 360


def path_flow_direction(bearing_deg: float, wind_from_deg: float) -> float:
    """Pick downwind orientation along a path."""
    blow = _blow_direction_deg(wind_from_deg)
    forward_diff = angle_diff_deg(blow, bearing_deg)
    reverse_diff = angle_diff_deg(blow, (bearing_deg + 180) % 360)
    if reverse_diff < forward_diff:
        return (bearing_deg + 180) % 360
    return bearing_deg


def _source_exposure(
    source_ids: list[int],
    exposure_by_feature: dict[int, dict],
) -> dict | None:
    best: dict | None = None
    best_risk = -1.0
    for fid in source_ids:
        row = exposure_by_feature.get(fid)
        if not row:
            continue
        risk = float(row.get("risk_score") or 0.0)
        if risk > best_risk:
            best_risk = risk
            best = row
    return best


def _geometry_fallback(
    path: PathRow,
    wind_from_deg: float,
) -> tuple[float, float, str, bool]:
    """Approximate flow from path bearing when exposure cache is missing."""
    align = alignment_score(wind_from_deg, path.bearing_deg)
    if align < 0.35:
        return (
            0.0,
            path.confidence * 0.5,
            "Wind crosses this corridor — weak scalar flow.",
            False,
        )
    energy = align * 0.5 * path.confidence
    conf = path.confidence * 0.55
    return (
        energy,
        conf,
        "Approximate flow from geometry alignment — run precompute-directions for model scores.",
        energy >= MIN_ENERGY and conf >= 0.3,
    )


def _base_energy(
    path: PathRow,
    exposure: dict | None,
    wind_from_deg: float,
) -> tuple[float, float, str, bool]:
    if exposure is None:
        return _geometry_fallback(path, wind_from_deg)

    handling = exposure.get("handling_mode", "normal_score")
    if handling == "excluded":
        return 0.0, exposure.get("confidence", path.confidence), (
            "Interior/covered geometry — scalar flow not modeled."
        ), False

    conf = float(exposure.get("confidence") or path.confidence)
    risk = float(exposure.get("risk_score") or 0.0)
    subscores = exposure.get("subscores") or {}
    align = float(subscores.get("directional_alignment") or 0.0)
    if align <= 0:
        align = alignment_score(wind_from_deg, path.bearing_deg)

    energy = align * (risk / 100.0) * conf
    if path.path_type in {"quay", "bridge"}:
        energy *= 1.1

    animate = handling not in {"excluded"} and conf >= MIN_CONFIDENCE and energy >= MIN_ENERGY
    if handling == "vector_preferred":
        animate = animate and energy >= 0.12
    if handling == "low_confidence":
        animate = animate and energy >= 0.14

    reason = "Wind likely channels along this corridor under the selected wind."
    cause_tags = exposure.get("cause_tags") or []
    if "river_aligned_wind" in cause_tags and path.path_type in {"quay", "bridge"}:
        reason = "Wind likely follows the river/quay corridor."
    if handling == "vector_preferred":
        reason = "Complex geometry — scalar street-flow is limited."
    if handling == "low_confidence":
        reason = "Low confidence — flow direction uncertain."

    return energy, conf, reason, animate


def _turn_factor(from_dir: float, to_dir: float) -> float:
    turn = angle_diff_deg(from_dir, to_dir)
    if turn <= TURN_SOFT_DEG:
        return 0.85
    if turn >= TURN_HARD_DEG:
        return 0.15
    return 0.45


def simulate_street_flow(
    paths: list[PathRow],
    exposure_by_feature: dict[int, dict],
    wind_from_deg: float,
) -> list[SimulatedFlow]:
    """Compute per-path meteor parameters with simple intersection relaxation."""
    edge_energy: dict[int, float] = {}
    edge_dir: dict[int, float] = {}
    edge_conf: dict[int, float] = {}
    edge_reason: dict[int, str] = {}
    edge_animate: dict[int, bool] = {}

    for path in paths:
        exposure = _source_exposure(path.source_feature_ids, exposure_by_feature)
        energy, conf, reason, animate = _base_energy(path, exposure, wind_from_deg)
        edge_energy[path.flow_path_id] = energy
        edge_dir[path.flow_path_id] = path_flow_direction(path.bearing_deg, wind_from_deg)
        edge_conf[path.flow_path_id] = conf
        edge_reason[path.flow_path_id] = reason
        edge_animate[path.flow_path_id] = animate

    outgoing: dict[int | None, list[int]] = {}
    incoming: dict[int | None, list[int]] = {}
    for path in paths:
        outgoing.setdefault(path.from_node_id, []).append(path.flow_path_id)
        incoming.setdefault(path.to_node_id, []).append(path.flow_path_id)

    node_ids = {nid for nid in outgoing if nid is not None} | {nid for nid in incoming if nid}
    for _ in range(RELAX_PASSES):
        for node_id in node_ids:
            in_edges = incoming.get(node_id, [])
            if not in_edges:
                continue
            in_energy = sum(edge_energy[eid] for eid in in_edges)
            if in_energy <= 0:
                continue
            outs = outgoing.get(node_id, [])
            if not outs:
                continue
            for out_id in outs:
                in_id = max(in_edges, key=lambda e: edge_energy[e])
                factor = _turn_factor(edge_dir[in_id], edge_dir[out_id])
                boosted = edge_energy[out_id] + in_energy * 0.35 * factor
                edge_energy[out_id] = min(1.5, boosted)

    results: list[SimulatedFlow] = []
    for path in paths:
        pid = path.flow_path_id
        energy = edge_energy[pid]
        conf = edge_conf[pid]
        animate = edge_animate[pid] and energy >= MIN_ENERGY
        density = min(1.0, 0.25 + energy * 0.9)
        results.append(
            SimulatedFlow(
                flow_path_id=pid,
                flow_direction_deg=edge_dir[pid],
                flow_strength=round(min(1.5, energy), 3),
                meteor_density=round(density, 3),
                confidence=round(conf, 3),
                animate=animate,
                reason=edge_reason[pid],
            ),
        )
    return results