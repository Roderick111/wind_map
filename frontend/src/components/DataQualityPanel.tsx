import type { DataQuality } from "../api/schemas";

type Props = {
  quality: DataQuality | null;
  loading: boolean;
  onClose: () => void;
};

export function DataQualityPanel({ quality, loading, onClose }: Props) {
  if (loading) {
    return (
      <aside className="quality-panel">
        <p>Loading data quality…</p>
      </aside>
    );
  }
  if (!quality) return null;

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <aside className="quality-panel">
      <header>
        <h2>Data quality</h2>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </header>
      <dl>
        <dt>Buildings</dt><dd>{quality.building_count}</dd>
        <dt>Official height</dt><dd>{pct(quality.official_height_coverage)}</dd>
        <dt>Estimated height</dt><dd>{pct(quality.estimated_height_coverage)}</dd>
        <dt>Fallback height</dt><dd>{pct(quality.fallback_height_coverage)}</dd>
        <dt>Missing height</dt><dd>{quality.missing_height_count}</dd>
        <dt>Streets with width</dt><dd>{quality.roads_with_inferred_width}</dd>
        <dt>Vegetation features</dt><dd>{quality.vegetation_count}</dd>
        <dt>Low-confidence zones</dt><dd>{quality.low_confidence_count}</dd>
      </dl>
      <section>
        <h3>Special geometry</h3>
        <ul>
          {Object.entries(quality.special_geometry_counts).map(([k, v]) => (
            <li key={k}>{k.replace(/_/g, " ")}: {v}</li>
          ))}
        </ul>
      </section>
    </aside>
  );
}