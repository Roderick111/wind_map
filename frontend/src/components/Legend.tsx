import { exposureColor, formatExposureClass } from "../lib/exposure";

const CLASSES = ["low", "medium", "high", "very_high"] as const;

type Props = {
  showGust: boolean;
};

export function Legend({ showGust }: Props) {
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