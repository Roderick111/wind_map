import type { TileManifest } from "../api/schemas";

export function tileDirectionsFromManifest(manifest: TileManifest | null): number[] {
  if (!manifest?.ready) return [];
  return Object.keys(manifest.exposure_pmtiles)
    .filter((k) => manifest.exposure_pmtiles[k])
    .map((k) => Number(k))
    .sort((a, b) => a - b);
}

export function canUseTileMode(
  manifest: TileManifest | null,
  tilesReady: boolean,
): boolean {
  const dirs = tileDirectionsFromManifest(manifest);
  if (dirs.length === 0) return false;
  return tilesReady || Boolean(manifest?.ready);
}

export function flowTilesReady(
  manifest: TileManifest | null,
  direction: number | null,
): boolean {
  if (!manifest || direction == null) return false;
  return Boolean(manifest.flow_pmtiles?.[String(direction)]);
}