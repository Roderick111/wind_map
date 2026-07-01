/** Normalize compass bearing to 0–359 (Open-Meteo may return 360). */
export function normalizeDirectionDeg(deg: number | null | undefined): number {
  if (deg == null || Number.isNaN(deg)) return 0;
  return ((Math.round(deg) % 360) + 360) % 360;
}

export function angleDiffDeg(a: number, b: number): number {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

export function snapDirection(deg: number, available: number[]): number {
  if (available.length === 0) return normalizeDirectionDeg(deg);
  return available.reduce(
    (best, d) => (angleDiffDeg(deg, d) < angleDiffDeg(deg, best) ? d : best),
    available[0],
  );
}

export function roundSpeedMs(speed: number | null | undefined): number {
  if (speed == null || Number.isNaN(speed)) return 0;
  return Math.round(speed * 10) / 10;
}