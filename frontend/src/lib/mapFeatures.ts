import type { FeatureResult } from "../api/schemas";

/** Feature types drawn on the exposure map (exclude building footprints). */
const MAP_FEATURE_TYPES = new Set([
  "street_segment",
  "bridge",
  "quay",
  "river",
  "open_space",
  "park",
  "tunnel",
  "vegetation",
  "open_exit_transition",
  "high_rise_cluster",
  "irregular_fabric_zone",
  "slope_zone",
]);

export function filterMapResults(results: FeatureResult[]): FeatureResult[] {
  return results.filter((r) => MAP_FEATURE_TYPES.has(r.feature_type));
}