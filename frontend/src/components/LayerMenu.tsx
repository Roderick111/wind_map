type Props = {
  showWindExposure: boolean;
  showConfidence: boolean;
  showSpecial: boolean;
  showGust: boolean;
  showBuildingExposure: boolean;
  showFlowInterpretation: boolean;
  showFlowAnimation: boolean;
  vectorFieldAvailable: boolean;
  pedestrianLayerAvailable: boolean;
  showVectorZones: boolean;
  showLabels: boolean;
  onToggleWindExposure: () => void;
  onToggleConfidence: () => void;
  onToggleSpecial: () => void;
  onToggleGust: () => void;
  onToggleBuildingExposure: () => void;
  onToggleFlowInterpretation: () => void;
  onToggleFlowAnimation: () => void;
  onToggleVectorZones: () => void;
  onToggleLabels: () => void;
};

export function LayerMenu({
  showWindExposure,
  showConfidence,
  showSpecial,
  showGust,
  showBuildingExposure,
  showFlowInterpretation,
  showFlowAnimation,
  vectorFieldAvailable,
  pedestrianLayerAvailable,
  showVectorZones,
  showLabels,
  onToggleWindExposure,
  onToggleConfidence,
  onToggleSpecial,
  onToggleGust,
  onToggleBuildingExposure,
  onToggleFlowInterpretation,
  onToggleFlowAnimation,
  onToggleVectorZones,
  onToggleLabels,
}: Props) {
  const flowAnimHint = vectorFieldAvailable
    ? "Computed vector field animation"
    : "Scalar flow streaks from corridor indicators — turn off Wind exposure to use as main view";

  return (
    <div className="layer-menu">
      <span className="layer-title">Layers</span>
      <label>
        <input type="checkbox" checked={showWindExposure} onChange={onToggleWindExposure} />
        Wind exposure
      </label>
      <label>
        <input type="checkbox" checked={showFlowInterpretation} onChange={onToggleFlowInterpretation} />
        Flow interpretation
      </label>
      <label title={flowAnimHint}>
        <input type="checkbox" checked={showFlowAnimation} onChange={onToggleFlowAnimation} />
        Flow animation
      </label>
      <label
        className={pedestrianLayerAvailable ? undefined : "layer-disabled"}
        title={pedestrianLayerAvailable
          ? "Pedestrian activity proxy from POIs and transit"
          : "Not built yet — planned POI/transit activity proxy (Phase 8)"}
      >
        <input
          type="checkbox"
          disabled={!pedestrianLayerAvailable}
          checked={false}
        />
        Pedestrian activity
      </label>
      <label><input type="checkbox" checked={showBuildingExposure} onChange={onToggleBuildingExposure} /> Building exposure</label>
      <label><input type="checkbox" checked={showConfidence} onChange={onToggleConfidence} /> Confidence</label>
      <label><input type="checkbox" checked={showSpecial} onChange={onToggleSpecial} /> Special geometry</label>
      <label><input type="checkbox" checked={showGust} onChange={onToggleGust} /> Gust risk</label>
      <label><input type="checkbox" checked={showVectorZones} onChange={onToggleVectorZones} /> Vector zones</label>
      <label><input type="checkbox" checked={showLabels} onChange={onToggleLabels} /> Labels</label>
    </div>
  );
}