import { useCallback, useEffect, useRef } from "react";
import type maplibregl from "maplibre-gl";
import type { FeatureResult } from "../api/schemas";
import {
  type StreetSegment,
  sampleAlongSegment,
  segmentsFromResults,
  streakLengthM,
  windForward,
} from "../lib/streetFlow";
import { exposureColor } from "../lib/exposure";

type Props = {
  map: maplibregl.Map | null;
  active: boolean;
  results: FeatureResult[];
  windDirectionDeg: number;
  useTileLayers: boolean;
};

type Particle = {
  segmentIndex: number;
  distanceM: number;
  phase: number;
};

const STREET_TILE_LAYER = "exposure-pmtiles-line";
const MAX_PARTICLES = 1400;

function mapStyleReady(map: maplibregl.Map | null): boolean {
  if (!map) return false;
  try {
    return Boolean(map.isStyleLoaded());
  } catch {
    return false;
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = Number.parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function segmentsFromTileFeatures(
  map: maplibregl.Map,
  windDirectionDeg: number,
): StreetSegment[] {
  if (!mapStyleReady(map)) return [];
  try {
    if (!map.getLayer(STREET_TILE_LAYER)) return [];
    const rendered = map.queryRenderedFeatures({ layers: [STREET_TILE_LAYER] });
    const segments: StreetSegment[] = [];
    for (const feat of rendered) {
      if (feat.geometry.type !== "LineString") continue;
      const ftype = String(feat.properties?.feature_type ?? "");
      if (!["street_segment", "quay", "bridge"].includes(ftype)) continue;
      const risk = Number(feat.properties?.risk_score ?? 0);
      if (risk < 35) continue;
      const coords = feat.geometry.coordinates as [number, number][];
      if (coords.length < 2) continue;
      segments.push({
        coords,
        color: exposureColor(String(feat.properties?.exposure_class ?? "medium")),
        speed: 12 + risk * 0.35,
        forward: windForward(coords, windDirectionDeg),
      });
      if (segments.length >= 900) break;
    }
    return segments;
  } catch {
    return [];
  }
}

function buildParticles(segments: StreetSegment[]): Particle[] {
  const particles: Particle[] = [];
  if (segments.length === 0) return particles;
  const perSeg = Math.max(1, Math.floor(MAX_PARTICLES / segments.length));
  for (let si = 0; si < segments.length; si += 1) {
    for (let i = 0; i < perSeg; i += 1) {
      particles.push({
        segmentIndex: si,
        distanceM: Math.random() * 120,
        phase: Math.random(),
      });
    }
  }
  return particles.slice(0, MAX_PARTICLES);
}

export function StreetWindFlow({
  map,
  active,
  results,
  windDirectionDeg,
  useTileLayers,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const segmentsRef = useRef<StreetSegment[]>([]);
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef(0);
  const lastTsRef = useRef(0);
  const resultsRef = useRef(results);
  const windRef = useRef(windDirectionDeg);
  const useTileLayersRef = useRef(useTileLayers);
  resultsRef.current = results;
  windRef.current = windDirectionDeg;
  useTileLayersRef.current = useTileLayers;

  const refreshSegments = useCallback(() => {
    if (!map || !mapStyleReady(map)) {
      segmentsRef.current = [];
      particlesRef.current = [];
      return;
    }

    let segments: StreetSegment[] = [];
    const fromResults = () => segmentsFromResults(resultsRef.current, windRef.current);

    if (useTileLayersRef.current) {
      segments = segmentsFromTileFeatures(map, windRef.current);
      if (segments.length === 0) {
        segments = fromResults();
      }
    } else {
      segments = fromResults();
    }

    segmentsRef.current = segments;
    particlesRef.current = buildParticles(segments);
  }, [map]);

  useEffect(() => {
    if (!active || !map || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      if (!mapStyleReady(map)) return;
      const rect = map.getContainer().getBoundingClientRect();
      canvas.width = rect.width * devicePixelRatio;
      canvas.height = rect.height * devicePixelRatio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      refreshSegments();
    };

    const onMapReady = () => {
      resize();
      refreshSegments();
    };

    if (mapStyleReady(map)) {
      resize();
    } else {
      map.once("load", onMapReady);
      map.once("styledata", onMapReady);
    }

    map.on("resize", resize);
    map.on("moveend", refreshSegments);
    map.on("zoomend", refreshSegments);
    map.on("idle", refreshSegments);

    const draw = (ts: number) => {
      if (!mapStyleReady(map)) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const dt = lastTsRef.current ? Math.min(0.05, (ts - lastTsRef.current) / 1000) : 0.016;
      lastTsRef.current = ts;

      const rect = map.getContainer().getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.fillStyle = "rgba(15, 23, 42, 0.08)";
      ctx.fillRect(0, 0, rect.width, rect.height);

      const segments = segmentsRef.current;
      const particles = particlesRef.current;
      const zoom = map.getZoom();

      for (const p of particles) {
        const seg = segments[p.segmentIndex];
        if (!seg) continue;

        p.distanceM += seg.speed * dt * seg.forward;
        if (p.distanceM < 0) p.distanceM += 500;
        if (p.distanceM > 500) p.distanceM -= 500;

        const head = sampleAlongSegment(seg.coords, p.distanceM, seg.forward);
        if (!head) continue;
        const tailDist = p.distanceM - streakLengthM(zoom, seg.speed) * seg.forward;
        const tail = sampleAlongSegment(seg.coords, tailDist, seg.forward);
        if (!tail) continue;

        const h = map.project([head.lng, head.lat]);
        const t = map.project([tail.lng, tail.lat]);
        if (
          h.x < -40 || h.y < -40 || h.x > rect.width + 40 || h.y > rect.height + 40
        ) continue;

        const pulse = 0.45 + 0.35 * Math.sin(ts * 0.002 + p.phase * 6.28);
        const grad = ctx.createLinearGradient(t.x, t.y, h.x, h.y);
        grad.addColorStop(0, hexToRgba(seg.color, 0));
        grad.addColorStop(0.35, hexToRgba(seg.color, 0.12 * pulse));
        grad.addColorStop(1, hexToRgba(seg.color, 0.55 * pulse));

        ctx.strokeStyle = grad;
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(t.x, t.y);
        ctx.lineTo(h.x, h.y);
        ctx.stroke();

        ctx.strokeStyle = hexToRgba("#e2e8f0", 0.18 * pulse);
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(t.x, t.y);
        ctx.lineTo(h.x, h.y);
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    refreshSegments();
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      lastTsRef.current = 0;
      map.off("load", onMapReady);
      map.off("styledata", onMapReady);
      map.off("resize", resize);
      map.off("moveend", refreshSegments);
      map.off("zoomend", refreshSegments);
      map.off("idle", refreshSegments);
    };
  }, [active, map, refreshSegments]);

  useEffect(() => {
    if (!active || !map) return;
    refreshSegments();
  }, [active, map, results, windDirectionDeg, useTileLayers, refreshSegments]);

  if (!active) return null;

  return <canvas ref={canvasRef} className="street-wind-canvas" aria-hidden />;
}