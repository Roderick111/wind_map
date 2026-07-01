type ValidationMetrics = {
  overall_accuracy: number;
  high_wind_recall: number | null;
  high_wind_precision: number | null;
  adjacent_class_accuracy: number;
  metrics_json: {
    baselines?: Record<string, {
      overall_accuracy: number;
      high_wind_recall: number | null;
    }>;
    confusion?: Record<string, Record<string, number>>;
  };
};

type Props = {
  metrics: ValidationMetrics | null;
  loading: boolean;
  onRun: () => void;
  onClose: () => void;
};

export function ValidationPanel({ metrics, loading, onRun, onClose }: Props) {
  return (
    <aside className="validation-panel data-quality-panel">
      <header>
        <h2>Validation</h2>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </header>
      <p className="panel-intro">
        Manual sanity checklist for Presqu&apos;île. Compares full scalar model to simpler baselines.
      </p>
      <button type="button" onClick={onRun} disabled={loading}>
        {loading ? "Running…" : "Run validation"}
      </button>
      {metrics && (
        <dl>
          <dt>Overall accuracy</dt>
          <dd>{(metrics.overall_accuracy * 100).toFixed(0)}%</dd>
          <dt>Adjacent class accuracy</dt>
          <dd>{(metrics.adjacent_class_accuracy * 100).toFixed(0)}%</dd>
          <dt>High-wind recall</dt>
          <dd>
            {metrics.high_wind_recall != null
              ? `${(metrics.high_wind_recall * 100).toFixed(0)}%`
              : "—"}
          </dd>
        </dl>
      )}
      {metrics?.metrics_json.baselines && (
        <section>
          <h3>Baselines vs full model</h3>
          <ul>
            {Object.entries(metrics.metrics_json.baselines).map(([key, row]) => (
              <li key={key}>
                {key.replace("predicted_", "").replace(/_/g, " ")}:{" "}
                {(row.overall_accuracy * 100).toFixed(0)}% accuracy
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}