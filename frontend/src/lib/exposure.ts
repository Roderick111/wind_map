import type { ExpressionSpecification } from "maplibre-gl";

/** Risk score 0–100: light green → yellow → hard red. */
export const EXPOSURE_RISK_STOPS: readonly [number, string][] = [
  [0, "#86efac"],
  [35, "#bef264"],
  [50, "#facc15"],
  [70, "#fb923c"],
  [100, "#dc2626"],
];

const STOP_RGB: readonly [number, [number, number, number]][] = [
  [0, [134, 239, 172]],
  [35, [190, 242, 100]],
  [50, [250, 204, 21]],
  [70, [251, 146, 60]],
  [100, [220, 38, 38]],
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function rgbToHex(r: number, g: number, b: number): string {
  const h = (n: number) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

/** Continuous map color from normalized risk score (0–100). */
export function riskScoreColor(score: number): string {
  const s = Math.max(0, Math.min(100, score));
  for (let i = 0; i < STOP_RGB.length - 1; i += 1) {
    const [s0, c0] = STOP_RGB[i];
    const [s1, c1] = STOP_RGB[i + 1];
    if (s <= s1) {
      const t = s1 === s0 ? 0 : (s - s0) / (s1 - s0);
      return rgbToHex(
        Math.round(lerp(c0[0], c1[0], t)),
        Math.round(lerp(c0[1], c1[1], t)),
        Math.round(lerp(c0[2], c1[2], t)),
      );
    }
  }
  const last = STOP_RGB[STOP_RGB.length - 1][1];
  return rgbToHex(last[0], last[1], last[2]);
}

/** MapLibre expression: interpolate risk_score to exposure color. */
export const EXPOSURE_RISK_COLOR_EXPR: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["coalesce", ["get", "risk_score"], 0],
  ...EXPOSURE_RISK_STOPS.flat(),
];

/** @deprecated Use riskScoreColor for map display; class buckets remain in API. */
export function exposureColor(cls: string): string {
  const fallback: Record<string, number> = {
    low: 12,
    medium: 38,
    high: 63,
    very_high: 88,
  };
  return riskScoreColor(fallback[cls] ?? 50);
}

export function confidenceOpacity(confidence: number): number {
  return 0.35 + confidence * 0.65;
}

export function formatExposureClass(cls: string): string {
  return cls.replace("_", " ");
}