import type { FeatureResult } from "../api/schemas";

const FLOW_TAG_TEXT: Record<string, string> = {
  wind_aligned_corridor: "Wind likely channels along this corridor.",
  river_aligned_wind: "Wind aligns with the river corridor here.",
  crosswind_discomfort: "Wind crosses the path — uncomfortable for pedestrians/cyclists.",
  open_exit_transition: "Sheltered street opens to a more exposed area.",
  gust_transition: "Sudden exposure change possible during gusts.",
  exposed_slope: "Windward slope increases exposure.",
  lee_shelter: "Lee side of slope may be more sheltered.",
  valley_channeling: "Valley geometry may channel wind along this axis.",
  ridge_exposure: "Ridge position increases exposure.",
  vector_model_preferred: "Scalar flow estimate is limited — vector model preferred.",
};

export function likelyFlowSummary(feature: FeatureResult, windDirectionDeg: number): string | null {
  if (feature.handling_mode === "excluded") {
    return "Interior or covered geometry — local airflow is not estimated.";
  }
  if (feature.handling_mode === "vector_preferred") {
    return "Complex geometry — scalar flow is limited; advanced vector modeling is preferred.";
  }

  const parts: string[] = [];
  for (const tag of feature.cause_tags) {
    const text = FLOW_TAG_TEXT[tag];
    if (text && !parts.includes(text)) parts.push(text);
  }

  if (feature.feature_type === "bridge" && feature.cause_tags.includes("crosswind_discomfort")) {
    parts.unshift(
      "Wind crosses this bridge from the side. This can feel uncomfortable for pedestrians and cyclists.",
    );
  } else if (
    feature.subscores.directional_alignment != null
    && Number(feature.subscores.directional_alignment) > 0.7
    && ["street_segment", "quay"].includes(feature.feature_type)
  ) {
    parts.unshift(
      `Wind likely channels along this ${feature.feature_type === "quay" ? "quay" : "street"} under the selected ${Math.round(windDirectionDeg)}° wind.`,
    );
  }

  if (parts.length === 0) {
    if (feature.confidence < 0.45) {
      return "Flow direction is uncertain at this location.";
    }
    return null;
  }

  const confLabel = feature.confidence >= 0.7 ? "high" : feature.confidence >= 0.5 ? "medium" : "low";
  return `${parts[0]} Confidence: ${confLabel}. Screening estimate only — not measured airflow.`;
}

export function windDirectionLabel(deg: number): string {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round(deg / 45) % 8;
  return dirs[idx];
}