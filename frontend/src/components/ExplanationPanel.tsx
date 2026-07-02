import type { FeatureResult } from "../api/schemas";
import { formatExposureClass, riskScoreColor } from "../lib/exposure";
import { likelyFlowSummary } from "../lib/flowInterpretation";

type Props = {
  feature: FeatureResult | null;
  windDirectionDeg: number;
  onClose: () => void;
  onReport: () => void;
};

export function ExplanationPanel({ feature, windDirectionDeg, onClose, onReport }: Props) {
  if (!feature) return null;
  const flowText = likelyFlowSummary(feature, windDirectionDeg);

  return (
    <aside className="explanation-panel">
      <header>
        <h2>{feature.name ?? feature.feature_type}</h2>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </header>
      <div
        className="exposure-badge"
        style={{ background: riskScoreColor(feature.risk_score) }}
      >
        {formatExposureClass(feature.exposure_class)} — {feature.risk_score.toFixed(0)}/100
      </div>
      <dl>
        <dt>Type</dt><dd>{feature.feature_type}</dd>
        <dt>Multiplier</dt><dd>{feature.local_multiplier.toFixed(2)}×</dd>
        <dt>Approx. local speed</dt><dd>{feature.approx_local_speed_ms?.toFixed(1) ?? "—"} m/s</dd>
        <dt>Confidence</dt><dd>{(feature.confidence * 100).toFixed(0)}%</dd>
        <dt>Handling</dt><dd>{feature.handling_mode.replace(/_/g, " ")}</dd>
        {feature.gust_sensitive && <><dt>Gust</dt><dd>Sensitive (geometry or forecast gusts)</dd></>}
      </dl>
      {feature.handling_mode === "vector_preferred" && (
        <p className="vector-note">
          Scalar screening only here — advanced vector model preferred for reliable local flow.
        </p>
      )}
      {flowText && (
        <section>
          <h3>Likely flow</h3>
          <p className="flow-summary">{flowText}</p>
        </section>
      )}
      {feature.cause_tags.length > 0 && (
        <section>
          <h3>Main causes</h3>
          <ul>{feature.cause_tags.map((t) => <li key={t}>{t.replace(/_/g, " ")}</li>)}</ul>
        </section>
      )}
      {feature.mitigation_tags.length > 0 && (
        <section>
          <h3>Mitigating factors</h3>
          <ul>{feature.mitigation_tags.map((t) => <li key={t}>{t.replace(/_/g, " ")}</li>)}</ul>
        </section>
      )}
      {feature.model_note && <p className="model-note">{feature.model_note}</p>}
      {feature.limitations.length > 0 && (
        <p className="limitations">{feature.limitations.join(" ")}</p>
      )}
      <button type="button" className="report-btn" onClick={onReport}>Report issue</button>
    </aside>
  );
}