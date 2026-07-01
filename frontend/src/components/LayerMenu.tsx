type Props = {
  showConfidence: boolean;
  showSpecial: boolean;
  showGust: boolean;
  showVectorZones: boolean;
  showLabels: boolean;
  onToggleConfidence: () => void;
  onToggleSpecial: () => void;
  onToggleGust: () => void;
  onToggleVectorZones: () => void;
  onToggleLabels: () => void;
};

export function LayerMenu({
  showConfidence,
  showSpecial,
  showGust,
  showVectorZones,
  showLabels,
  onToggleConfidence,
  onToggleSpecial,
  onToggleGust,
  onToggleVectorZones,
  onToggleLabels,
}: Props) {
  return (
    <div className="layer-menu">
      <span className="layer-title">Layers</span>
      <label><input type="checkbox" checked={showConfidence} onChange={onToggleConfidence} /> Confidence</label>
      <label><input type="checkbox" checked={showSpecial} onChange={onToggleSpecial} /> Special geometry</label>
      <label><input type="checkbox" checked={showGust} onChange={onToggleGust} /> Gust risk</label>
      <label><input type="checkbox" checked={showVectorZones} onChange={onToggleVectorZones} /> Vector zones</label>
      <label><input type="checkbox" checked={showLabels} onChange={onToggleLabels} /> Labels</label>
    </div>
  );
}