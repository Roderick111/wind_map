export type MapViewMode = "exposure" | "flow" | "base";

type Props = {
  mapViewMode: MapViewMode;
  showLabels: boolean;
  onMapViewModeChange: (mode: MapViewMode) => void;
  onToggleLabels: () => void;
};

export function LayerMenu({
  mapViewMode,
  showLabels,
  onMapViewModeChange,
  onToggleLabels,
}: Props) {
  return (
    <div className="layer-menu">
      <span className="layer-title">Map view</span>
      <label>
        <input
          type="radio"
          name="map-view"
          checked={mapViewMode === "exposure"}
          onChange={() => onMapViewModeChange("exposure")}
        />
        Exposure colors
      </label>
      <label>
        <input
          type="radio"
          name="map-view"
          checked={mapViewMode === "flow"}
          onChange={() => onMapViewModeChange("flow")}
        />
        Flow on streets
      </label>
      <label>
        <input
          type="radio"
          name="map-view"
          checked={mapViewMode === "base"}
          onChange={() => onMapViewModeChange("base")}
        />
        Base map only
      </label>
      <span className="layer-title">Options</span>
      <label>
        <input type="checkbox" checked={showLabels} onChange={onToggleLabels} />
        Street labels
      </label>
      <p className="layer-note">
        Flow view replaces colored streets with arrows along corridors. Screening estimate — not CFD.
      </p>
    </div>
  );
}