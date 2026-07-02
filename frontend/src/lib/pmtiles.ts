import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";
import { EXPOSURE_RISK_COLOR_EXPR } from "./exposure";

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

/** Continuous risk_score → color (see exposure.ts). */
export const EXPOSURE_COLOR_EXPR: maplibregl.ExpressionSpecification = EXPOSURE_RISK_COLOR_EXPR;