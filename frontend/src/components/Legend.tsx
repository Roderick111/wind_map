import { exposureColor, formatExposureClass } from "../lib/exposure";
import type { MapViewMode } from "./LayerMenu";

const CLASSES = ["low", "medium", "high", "very_high"] as const;

type Props = {
  mapViewMode: MapViewMode;
};

export function Legend({ mapViewMode }: Props) {
  if (mapViewMode === "flow") {
    return (
      <div className="legend">
        <h3>Flow on streets</h3>
        <p className="legend-hint">Arrows run along street centerlines in likely flow direction.</p>
        <ul>
          {CLASSES.map((cls) => (
            <li key={cls}>
              <span className="legend-swatch" style={{ background: exposureColor(cls) }} />
              {formatExposureClass(cls)} corridor
            </li>
          ))}
        </ul>
        <p className="legend-hint">Click a street, quay, bridge, or square for details.</p>
      </div>
    );
  }

  if (mapViewMode === "base") {
    return (
      <div className="legend">
        <h3>Base map</h3>
        <p className="legend-hint">Pick Exposure colors or Flow on streets to see wind screening.</p>
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
      <p className="legend-hint">Click a street, quay, bridge, or square for details.</p>
    </div>
  );
}