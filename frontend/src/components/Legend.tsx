import { exposureColor, formatExposureClass } from "../lib/exposure";

const CLASSES = ["low", "medium", "high", "very_high"] as const;

type Props = {
  showGust: boolean;
  showWindExposure: boolean;
  showFlowAnimation: boolean;
};

export function Legend({ showGust, showWindExposure, showFlowAnimation }: Props) {
  if (!showWindExposure && showFlowAnimation) {
    return (
      <div className="legend">
        <h3>Flow animation</h3>
        <p className="legend-hint">Animated streaks show likely flow direction. Screening estimate — not CFD.</p>
      </div>
    );
  }

  if (!showWindExposure) {
    return (
      <div className="legend">
        <h3>Base map</h3>
        <p className="legend-hint">Wind exposure layer is off. Enable Flow interpretation or Flow animation.</p>
      </div>
    );
  }

  return (
    <div className="legend">
      <h3>Wind exposure</h3>
      <p className="legend-hint">Colors = estimated exposure class for current wind</p>
      <ul>
        {CLASSES.map((cls) => (
          <li key={cls}>
            <span className="legend-swatch" style={{ background: exposureColor(cls) }} />
            {formatExposureClass(cls)}
          </li>
        ))}
      </ul>
      {showGust && (
        <p className="legend-gust">
          <span className="legend-swatch gust" />
          Gust-sensitive
        </p>
      )}
      <p className="legend-hint">Click a street, quay, bridge, or square for details.</p>
    </div>
  );
}