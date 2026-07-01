import { windDirectionLabel } from "../lib/flowInterpretation";

type Props = {
  direction: number;
  speed: number;
  gustMs: number | null;
  cacheDirection: number | null;
  visible: boolean;
};

export function WindFlowOverlay({
  direction,
  speed,
  gustMs,
  cacheDirection,
  visible,
}: Props) {
  if (!visible) return null;

  return (
    <div className="wind-flow-overlay" aria-label="Wind direction indicator">
      <div
        className="wind-flow-compass"
        style={{ transform: `rotate(${direction}deg)` }}
        title={`${windDirectionLabel(direction)} wind`}
      >
        ↑
      </div>
      <div className="wind-flow-label">
        <strong>{windDirectionLabel(direction)}</strong>
        <span>{direction}° @ {speed.toFixed(1)} m/s</span>
        {gustMs != null && gustMs > 0 && (
          <span className="wind-flow-gust">gust {gustMs.toFixed(1)} m/s</span>
        )}
        {cacheDirection != null && cacheDirection !== direction && (
          <span className="wind-flow-snap">tiles @ {cacheDirection}°</span>
        )}
      </div>
      <p className="wind-flow-disclaimer">Likely flow patterns — screening estimate, not CFD</p>
    </div>
  );
}