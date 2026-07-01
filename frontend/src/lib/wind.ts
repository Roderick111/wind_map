/** Normalize compass bearing to 0–359 (Open-Meteo may return 360). */
export function normalizeDirectionDeg(deg: number | null | undefined): number {
  if (deg == null || Number.isNaN(deg)) return 0;
  return ((Math.round(deg) % 360) + 360) % 360;
}

export function roundSpeedMs(speed: number | null | undefined): number {
  if (speed == null || Number.isNaN(speed)) return 0;
  return Math.round(speed * 10) / 10;
}