import type { FlowPath } from "../api/schemas";

type LngLat = [number, number];
type GeoPoint = { lng: number; lat: number };

/** Street-level zoom — meteors only render at or above this. */
export const METEOR_MIN_ZOOM = 14;

/** Faint path guides visible from this zoom upward. */
export const FLOW_PATH_MIN_ZOOM = 14;

export type MeteorDrawStyle = {
  minPx: number;
  maxPx: number;
  lineWidth: number;
  haloWidth: number;
};

/** Screen-pixel sizing scales with zoom so dashes stay readable on streets. */
export function meteorDrawStyle(zoom: number): MeteorDrawStyle {
  const t = Math.max(0, zoom - METEOR_MIN_ZOOM);
  return {
    minPx: 32 + t * 11,
    maxPx: 54 + t * 18,
    lineWidth: 2.4 + t * 0.5,
    haloWidth: 5.5 + t * 1.2,
  };
}

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

function angleDiff(a: number, b: number): number {
  return Math.abs(((a - b + 180) % 360) - 180);
}

export function pathCoords(path: FlowPath): LngLat[] {
  const geom = path.geom;
  if (geom.type !== "LineString") return [];
  return geom.coordinates as LngLat[];
}

export function pathLengthM(coords: LngLat[]): number {
  let total = 0;
  for (let i = 1; i < coords.length; i += 1) {
    total += haversineM(coords[i - 1], coords[i]);
  }
  return total;
}

export function flowForward(path: FlowPath): 1 | -1 {
  const diff = angleDiff(path.flow_direction_deg, path.bearing_deg);
  return diff <= 90 ? 1 : -1;
}

/** Sample a point along a path without wrapping past endpoints. */
export function interpolateAtDistance(coords: LngLat[], distanceM: number): GeoPoint | null {
  if (coords.length < 2) return null;
  const total = pathLengthM(coords);
  if (total <= 0) return null;
  const d = Math.max(0, Math.min(distanceM, total));

  let acc = 0;
  for (let i = 1; i < coords.length; i += 1) {
    const segLen = haversineM(coords[i - 1], coords[i]);
    if (acc + segLen >= d) {
      const t = segLen > 0 ? (d - acc) / segLen : 0;
      return {
        lng: coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t,
        lat: coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t,
      };
    }
    acc += segLen;
  }
  const last = coords[coords.length - 1];
  return { lng: last[0], lat: last[1] };
}

export function meteorCount(path: FlowPath, zoom = 16): number {
  if (!path.animate) return 0;
  const zoomBoost = zoom < 15 ? 0.7 : zoom < 16 ? 1 : 1.15;
  return Math.max(
    2,
    Math.round((path.length_m / 32) * path.meteor_density * 2.4 * zoomBoost),
  );
}

/** Meters per second drift along the path centerline. */
export function meteorSpeedMps(path: FlowPath): number {
  return 2.5 + path.flow_strength * 9;
}

/** Meteor tail in meters — screen-space cap prevents cross-block lasers. */
export function meteorStreakM(path: FlowPath): number {
  return 14 + path.flow_strength * 18;
}

export function meteorOpacity(path: FlowPath): number {
  return Math.min(0.95, 0.68 + path.confidence * 0.12 + path.flow_strength * 0.22);
}

export type MeteorSegment = {
  head: GeoPoint;
  tail: GeoPoint;
  forward: 1 | -1;
};

/** Head/tail along path with clamped tail — no wrap-around streaks. */
export function meteorSegment(path: FlowPath, progress: number): MeteorSegment | null {
  const coords = pathCoords(path);
  const total = pathLengthM(coords);
  if (total <= 0 || coords.length < 2) return null;

  const forward = flowForward(path);
  const p = ((progress % 1) + 1) % 1;
  const headDist = forward > 0 ? p * total : (1 - p) * total;
  const streak = meteorStreakM(path);
  const tailDist = forward > 0
    ? Math.max(0, headDist - streak)
    : Math.min(total, headDist + streak);

  const head = interpolateAtDistance(coords, headDist);
  const tail = interpolateAtDistance(coords, tailDist);
  if (!head || !tail) return null;
  return { head, tail, forward };
}

export type PathBounds = { west: number; east: number; south: number; north: number };

export function pathBounds(coords: LngLat[]): PathBounds | null {
  if (coords.length === 0) return null;
  let west = coords[0][0];
  let east = coords[0][0];
  let south = coords[0][1];
  let north = coords[0][1];
  for (const [lng, lat] of coords) {
    west = Math.min(west, lng);
    east = Math.max(east, lng);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return { west, east, south, north };
}

export function boundsOverlap(
  a: PathBounds,
  west: number,
  south: number,
  east: number,
  north: number,
): boolean {
  return a.west <= east && a.east >= west && a.south <= north && a.north >= south;
}

/** Normalize streak to windy-style dash length in screen pixels. */
export function normalizeStreakPixels(
  head: { x: number; y: number },
  tail: { x: number; y: number },
  style: MeteorDrawStyle,
  lengthScale = 1,
): { x: number; y: number } {
  const dx = head.x - tail.x;
  const dy = head.y - tail.y;
  const len = Math.hypot(dx, dy);
  if (len <= 0) return tail;
  const minPx = style.minPx * lengthScale;
  const maxPx = style.maxPx * lengthScale;
  const target = Math.max(minPx, Math.min(maxPx, len));
  const ratio = target / len;
  return { x: head.x - dx * ratio, y: head.y - dy * ratio };
}

export type ViewportBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type PathCache = {
  bounds: PathBounds | null;
  totalM: number;
};

export function buildPathCache(paths: FlowPath[]): PathCache[] {
  return paths.map((path) => {
    const coords = pathCoords(path);
    return {
      bounds: pathBounds(coords),
      totalM: pathLengthM(coords),
    };
  });
}

const MAX_VIEWPORT_PARTICLES = 3200;

function shuffleIndices(indices: number[]): void {
  for (let i = indices.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [indices[i], indices[j]] = [indices[j], indices[i]];
  }
}

export type FlowParticle = {
  pathIndex: number;
  progress: number;
  phase: number;
};

/** Build meteors only for animate paths visible in the current viewport. */
export function buildViewportParticles(
  paths: FlowPath[],
  caches: PathCache[],
  viewport?: ViewportBounds,
  zoom = 16,
): FlowParticle[] {
  const visible: number[] = [];
  for (let pi = 0; pi < paths.length; pi += 1) {
    const path = paths[pi];
    if (!path.animate) continue;
    const cache = caches[pi];
    if (viewport && cache?.bounds) {
      if (!boundsOverlap(
        cache.bounds,
        viewport.west,
        viewport.south,
        viewport.east,
        viewport.north,
      )) {
        continue;
      }
    }
    visible.push(pi);
  }
  shuffleIndices(visible);

  const particles: FlowParticle[] = [];
  for (const pi of visible) {
    const path = paths[pi];
    const count = meteorCount(path, zoom);
    for (let i = 0; i < count; i += 1) {
      particles.push({
        pathIndex: pi,
        progress: (i + Math.random() * 0.5) / count,
        phase: 0.75 + Math.random() * 0.5,
      });
      if (particles.length >= MAX_VIEWPORT_PARTICLES) return particles;
    }
  }
  return particles;
}

export function flowPathsToGeoJSON(paths: FlowPath[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: paths.map((path) => ({
      type: "Feature",
      id: path.flow_path_id,
      geometry: path.geom as unknown as GeoJSON.Geometry,
      properties: {
        flow_path_id: path.flow_path_id,
        path_type: path.path_type,
        animate: path.animate,
        confidence: path.confidence,
      },
    })),
  };
}