import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";

let protocolReady = false;

export function ensurePmtilesProtocol(): void {
  if (protocolReady) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  protocolReady = true;
}

export function pmtilesUrl(areaSlug: string, filename: string): string {
  return `pmtiles://${window.location.origin}/api/tiles/${areaSlug}/${filename}`;
}

export const EXPOSURE_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "match",
  ["get", "exposure_class"],
  "low", "#4ade80",
  "medium", "#facc15",
  "high", "#fb923c",
  "very_high", "#ef4444",
  "#94a3b8",
];