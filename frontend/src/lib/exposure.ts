const EXPOSURE_COLORS: Record<string, string> = {
  low: "#4ade80",
  medium: "#facc15",
  high: "#fb923c",
  very_high: "#ef4444",
};

export function exposureColor(cls: string): string {
  return EXPOSURE_COLORS[cls] ?? "#94a3b8";
}

export function confidenceOpacity(confidence: number): number {
  return 0.35 + confidence * 0.65;
}

export function formatExposureClass(cls: string): string {
  return cls.replace("_", " ");
}