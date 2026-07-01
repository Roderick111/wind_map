import type { FeatureResult } from "../api/schemas";
import { exposureColor } from "./exposure";

const STREET_TYPES = new Set(["street_segment", "quay", "bridge"]);
const MAX_SEGMENTS = 900;
const MIN_RISK = 35;

export type StreetSegment = {
  coords: [number, number][];
  color: string;
  speed: number;
  forward: 1 | -1;
};

type LngLat = [number, number];

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function haversineM(a: LngLat, b: LngLat): number {
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const dlat = lat2 - lat1;
  const dlon = toRad(b[0] - a[0]);
  const h = Math.sin(dlat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
  return 6_371_000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function segmentLengthM(coords: LngLat[]): number {
  let total = 0;
  for (let i = 1; i < coords.length; i += 1) {
    total += haversineM(coords[i - 1], coords[i]);
  }
  return total;
}

function bearingDeg(a: LngLat, b: LngLat): number {
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const dlon = toRad(b[0] - a[0]);
  const y = Math.sin(dlon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dlon);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export function windForward(coords: LngLat[], windDeg: number): 1 | -1 {
  if (coords.length < 2) return 1;
  const lineBearing = bearingDeg(coords[0], coords[coords.length - 1]);
  const diff = Math.abs(((windDeg - lineBearing + 540) % 360) - 180);
  if (diff > 110) return 1;
  const mid = Math.floor(coords.length / 2);
  const local = bearingDeg(coords[Math.max(0, mid - 1)], coords[mid]);
  const delta = ((windDeg - local + 540) % 360) - 180;
  return delta >= 0 ? 1 : -1;
}

function lineCoords(geom: FeatureResult["geom"]): LngLat[] | null {
  if (geom.type === "LineString") {
    return geom.coordinates as LngLat[];
  }
  return null;
}

export function segmentsFromResults(
  results: FeatureResult[],
  windDirectionDeg: number,
): StreetSegment[] {
  const segments: StreetSegment[] = [];
  for (const row of results) {
    if (!STREET_TYPES.has(row.feature_type)) continue;
    if (row.risk_score < MIN_RISK) continue;
    const coords = lineCoords(row.geom);
    if (!coords || coords.length < 2) continue;
    if (segmentLengthM(coords) < 25) continue;
    segments.push({
      coords,
      color: exposureColor(row.exposure_class),
      speed: 12 + row.risk_score * 0.35,
      forward: windForward(coords, windDirectionDeg),
    });
    if (segments.length >= MAX_SEGMENTS) break;
  }
  return segments;
}

export type SegmentSample = {
  lng: number;
  lat: number;
  bearing: number;
};

export function sampleAlongSegment(
  coords: LngLat[],
  distanceM: number,
  forward: 1 | -1,
): SegmentSample | null {
  if (coords.length < 2) return null;
  const total = segmentLengthM(coords);
  if (total <= 0) return null;

  let d = ((distanceM % total) + total) % total;
  if (forward < 0) d = total - d;

  let acc = 0;
  for (let i = 1; i < coords.length; i += 1) {
    const a = coords[i - 1];
    const b = coords[i];
    const len = haversineM(a, b);
    if (acc + len >= d) {
      const t = len > 0 ? (d - acc) / len : 0;
      return {
        lng: a[0] + (b[0] - a[0]) * t,
        lat: a[1] + (b[1] - a[1]) * t,
        bearing: bearingDeg(a, b),
      };
    }
    acc += len;
  }
  const last = coords[coords.length - 1];
  const prev = coords[coords.length - 2];
  return { lng: last[0], lat: last[1], bearing: bearingDeg(prev, last) };
}

export function streakLengthM(zoom: number, speed: number): number {
  const base = 18 + speed * 0.08;
  return base * Math.max(0.55, 1.4 - zoom * 0.08);
}