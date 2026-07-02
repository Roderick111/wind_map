import type { MapViewMode } from "./LayerMenu";

type Props = {
  mapViewMode: MapViewMode;
};

export function Legend({ mapViewMode }: Props) {
  if (mapViewMode === "flow") {
    return (
      <div className="legend">
        <h3>Wind flow</h3>
        <p className="legend-hint">
          Zoom in to street level to see meteors along each path. At city zoom the map stays clean.
        </p>
        <p className="legend-hint">Click a street, quay, bridge, or square for exposure details.</p>
      </div>
    );
  }

  if (mapViewMode === "base") {
    return (
      <div className="legend">
        <h3>Base map</h3>
        <p className="legend-hint">Pick Exposure colors or Wind flow to see wind screening.</p>
      </div>
    );
  }

  return (
    <div className="legend">
      <h3>Wind exposure</h3>
      <p className="legend-hint">Color scale = estimated exposure score (0–100) for current wind</p>
      <div className="legend-gradient" aria-hidden />
      <div className="legend-gradient-labels">
        <span>Lower</span>
        <span>Higher</span>
      </div>
      <p className="legend-hint">Click a street, quay, bridge, or square for details.</p>
    </div>
  );
}