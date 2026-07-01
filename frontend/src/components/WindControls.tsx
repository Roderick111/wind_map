type WindMode = "manual" | "current" | "forecast"; // UI mode; API maps "current" → current_weather

function formatForecastTime(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

type Props = {
  mode: WindMode;
  direction: number;
  speed: number;
  forecastHour: number;
  forecastHours: number;
  forecastTimestamp: string | null;
  loading: boolean;
  cacheReady: boolean;
  cacheDirection: number | null;
  onModeChange: (mode: WindMode) => void;
  onDirectionChange: (deg: number) => void;
  onSpeedChange: (ms: number) => void;
  onForecastHourChange: (hour: number) => void;
};

export function WindControls({
  mode,
  direction,
  speed,
  forecastHour,
  forecastHours,
  forecastTimestamp,
  loading,
  cacheReady,
  cacheDirection,
  onModeChange,
  onDirectionChange,
  onSpeedChange,
  onForecastHourChange,
}: Props) {
  return (
    <div className="wind-controls">
      <div className="segmented">
        {(["manual", "current", "forecast"] as WindMode[]).map((m) => (
          <button
            key={m}
            type="button"
            className={mode === m ? "active" : ""}
            onClick={() => onModeChange(m)}
          >
            {m}
          </button>
        ))}
      </div>
      <label>
        Direction {direction}°
        <input
          type="range"
          min={0}
          max={359}
          value={direction}
          onChange={(e) => onDirectionChange(Number(e.target.value))}
          disabled={mode !== "manual"}
        />
      </label>
      <label>
        Speed {speed.toFixed(1)} m/s
        <input
          type="range"
          min={0}
          max={25}
          step={0.5}
          value={speed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
          disabled={mode !== "manual"}
        />
      </label>
      {mode === "forecast" && (
        <>
          <label>
            Forecast +{forecastHour}h
            <input
              type="range"
              min={0}
              max={Math.max(forecastHours - 1, 0)}
              value={forecastHour}
              onChange={(e) => onForecastHourChange(Number(e.target.value))}
            />
          </label>
          <p className="live-wind forecast-wind">
            Open-Meteo forecast
            {forecastTimestamp ? ` ${formatForecastTime(forecastTimestamp)}` : ""}
            : {direction}° @ {speed.toFixed(1)} m/s
          </p>
        </>
      )}
      {mode === "current" && (
        <p className="live-wind">Live Open-Meteo: {direction}° @ {speed.toFixed(1)} m/s</p>
      )}
      {cacheReady && (
        <p className="cache-hint">
          Instant cache
          {cacheDirection !== null && direction !== cacheDirection
            ? ` (snapped to ${cacheDirection}°)`
            : ""}
        </p>
      )}
      {loading && <span className="loading">Updating exposure…</span>}
    </div>
  );
}