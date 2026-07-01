import { useCallback, useEffect, useRef, useState } from "react";
import {
  createScenario,
  getAreaLayers,
  getAreaSummary,
  getAreas,
  getCachedExposure,
  getFlowIndicators,
  getTileManifest,
  getCurrentWeather,
  getForecastWeather,
  getDataQuality,
  getValidationCases,
  runValidation,
  seedValidation,
  getScenarioResults,
  refreshWeather,
  submitFeedback,
} from "./api/client";
import { filterMapResults } from "./lib/mapFeatures";
import { canUseTileMode, flowTilesReady, tileDirectionsFromManifest } from "./lib/tiles";
import { normalizeDirectionDeg, roundSpeedMs, snapDirection } from "./lib/wind";
import type { Area, DataQuality, FeatureResult, FlowIndicator, TileManifest, Weather } from "./api/schemas";
import { DataQualityPanel } from "./components/DataQualityPanel";
import { ValidationPanel } from "./components/ValidationPanel";
import { ExplanationPanel } from "./components/ExplanationPanel";
import { LayerMenu } from "./components/LayerMenu";
import { Legend } from "./components/Legend";
import { MapView } from "./components/MapView";
import { WindFlowOverlay } from "./components/WindFlowOverlay";
import { WindControls } from "./components/WindControls";

type WindMode = "manual" | "current_weather" | "forecast";
type WindModeUi = "manual" | "current" | "forecast";
type View = "map" | "accuracy" | "quality" | "validation";

const WEATHER_REFRESH_MS = 10 * 60 * 1000;

export default function App() {
  const [area, setArea] = useState<Area | null>(null);
  const [mode, setMode] = useState<WindModeUi>("manual");
  const [direction, setDirection] = useState(90);
  const [speed, setSpeed] = useState(8);
  const [forecastHour, setForecastHour] = useState(0);
  const [forecastHours, setForecastHours] = useState(48);
  const [forecastTimestamp, setForecastTimestamp] = useState<string | null>(null);
  const [, setScenarioId] = useState<number | null>(null);
  const [results, setResults] = useState<FeatureResult[]>([]);
  const [vectorZones, setVectorZones] = useState<
    {
      id: number;
      name: string;
      zone_type: string;
      status: string;
      vector_field_available: boolean;
      boundary: GeoJSON.Geometry;
    }[]
  >([]);
  const [selected, setSelected] = useState<FeatureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("map");
  const [showConfidence, setShowConfidence] = useState(true);
  const [showSpecial, setShowSpecial] = useState(true);
  const [showGust, setShowGust] = useState(false);
  const [showBuildingExposure, setShowBuildingExposure] = useState(false);
  const [showFlowInterpretation, setShowFlowInterpretation] = useState(false);
  const [flowIndicators, setFlowIndicators] = useState<FlowIndicator[]>([]);
  const [showVectorZones, setShowVectorZones] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [areaMetaReady, setAreaMetaReady] = useState(false);
  const [quality, setQuality] = useState<DataQuality | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsImport, setNeedsImport] = useState(false);
  const [cacheReady, setCacheReady] = useState(false);
  const [tilesReady, setTilesReady] = useState(false);
  const [tileManifest, setTileManifest] = useState<TileManifest | null>(null);
  const [useTileLayers, setUseTileLayers] = useState(false);
  const [tileDirection, setTileDirection] = useState<number | null>(null);
  const [cacheDirection, setCacheDirection] = useState<number | null>(null);
  const [windGustMs, setWindGustMs] = useState<number | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [validationMetrics, setValidationMetrics] = useState<{
    overall_accuracy: number;
    high_wind_recall: number | null;
    high_wind_precision: number | null;
    adjacent_class_accuracy: number;
    metrics_json: Record<string, unknown>;
  } | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);

  const areaRef = useRef<Area | null>(null);
  const cacheReadyRef = useRef(false);
  const tilesReadyRef = useRef(false);
  const directionRef = useRef(direction);
  const speedRef = useRef(speed);
  const forecastsRef = useRef<Weather[]>([]);
  const weatherRefreshAtRef = useRef(0);
  const exposureRequestRef = useRef(0);
  const tileManifestRef = useRef<TileManifest | null>(null);

  useEffect(() => { areaRef.current = area; }, [area]);
  useEffect(() => { cacheReadyRef.current = cacheReady; }, [cacheReady]);
  useEffect(() => { tilesReadyRef.current = tilesReady; }, [tilesReady]);
  useEffect(() => { directionRef.current = direction; }, [direction]);
  useEffect(() => { speedRef.current = speed; }, [speed]);
  useEffect(() => { tileManifestRef.current = tileManifest; }, [tileManifest]);

  useEffect(() => {
    getAreas().then((list) => {
      setAreas(list);
      const preferred = list.find((a) => a.slug === "lyon_full")
        ?? list.find((a) => a.slug === "pilot_presquile")
        ?? list[0];
      setArea(preferred ?? null);
    }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!area) {
      setAreaMetaReady(false);
      return;
    }

    let cancelled = false;
    setAreaMetaReady(false);
    setTileManifest(null);
    setUseTileLayers(false);
    setTileDirection(null);
    setCacheDirection(null);
    setResults([]);
    setShowBuildingExposure(false);
    if (area.slug === "lyon_full") {
      setShowVectorZones(false);
      setShowLabels(false);
    } else {
      setShowVectorZones(true);
      setShowLabels(true);
    }

    void Promise.all([
      getAreaLayers(area.id).then((layers) => {
        if (!cancelled) setVectorZones(layers.vector_zones);
      }),
      getTileManifest(area.slug)
        .then((manifest) => { if (!cancelled) setTileManifest(manifest); })
        .catch(() => { if (!cancelled) setTileManifest(null); }),
      getAreaSummary(area.id)
        .then((s) => {
          if (cancelled) return;
          setNeedsImport(s.needs_osm_import);
          setCacheReady(s.cache_ready);
          setTilesReady(s.tiles_ready ?? false);
        })
        .catch(() => {
          if (cancelled) return;
          setNeedsImport(false);
          setCacheReady(false);
          setTilesReady(false);
        }),
    ]).finally(() => {
      if (!cancelled) setAreaMetaReady(true);
    });

    return () => { cancelled = true; };
  }, [area]);

  useEffect(() => {
    if (!area || view !== "quality") return;
    setQualityLoading(true);
    getDataQuality(area.id)
      .then(setQuality)
      .catch((e) => setError(String(e)))
      .finally(() => setQualityLoading(false));
  }, [area, view]);

  const applyWindIfCurrent = useCallback((
    requestId: number,
    dir: number,
    spd: number,
    timestamp: string | null = null,
  ) => {
    if (requestId !== exposureRequestRef.current) return;
    setDirection(dir);
    setSpeed(spd);
    setForecastTimestamp(timestamp);
  }, []);

  const loadExposure = useCallback(async (
    runMode: WindModeUi,
    hourIndex = 0,
    forceWeatherRefresh = false,
  ) => {
    const currentArea = areaRef.current;
    if (!currentArea) return;

    const requestId = ++exposureRequestRef.current;
    const useCache = cacheReadyRef.current;
    setLoading(true);
    if (!useCache) {
      setResults([]);
      setCacheDirection(null);
    }
    setError(null);

    try {
      let resolvedDir = normalizeDirectionDeg(directionRef.current);
      let resolvedSpeed = speedRef.current;
      let resolvedGust: number | null = runMode === "manual" ? null : windGustMs;
      let scenarioType: WindMode = runMode === "current" ? "current_weather" : runMode;

      if (runMode === "current") {
        try {
          const now = Date.now();
          if (forceWeatherRefresh || now - weatherRefreshAtRef.current > WEATHER_REFRESH_MS) {
            await refreshWeather(currentArea.id);
            weatherRefreshAtRef.current = now;
          }
          const wx = await getCurrentWeather(currentArea.id);
          if (requestId !== exposureRequestRef.current) return;
          resolvedDir = normalizeDirectionDeg(wx.wind_direction_10m_deg);
          resolvedSpeed = roundSpeedMs(wx.wind_speed_10m_ms);
          resolvedGust = wx.wind_gust_10m_ms ?? null;
          setWindGustMs(resolvedGust);
          applyWindIfCurrent(requestId, resolvedDir, resolvedSpeed, null);
        } catch {
          if (requestId !== exposureRequestRef.current) return;
          setError("Weather unavailable — using manual values");
          scenarioType = "manual";
        }
      } else if (runMode === "forecast") {
        try {
          if (forecastsRef.current.length === 0 || forceWeatherRefresh) {
            await refreshWeather(currentArea.id);
            weatherRefreshAtRef.current = Date.now();
            forecastsRef.current = await getForecastWeather(currentArea.id);
            if (requestId !== exposureRequestRef.current) return;
            setForecastHours(forecastsRef.current.length || 48);
          }
          const hour = forecastsRef.current[hourIndex];
          if (!hour) throw new Error("No forecast hour available");
          resolvedDir = normalizeDirectionDeg(hour.wind_direction_10m_deg);
          resolvedSpeed = roundSpeedMs(hour.wind_speed_10m_ms);
          resolvedGust = hour.wind_gust_10m_ms ?? null;
          setWindGustMs(resolvedGust);
          applyWindIfCurrent(
            requestId,
            resolvedDir,
            resolvedSpeed,
            hour.forecast_timestamp ?? null,
          );
        } catch {
          if (requestId !== exposureRequestRef.current) return;
          setError("Forecast unavailable — try again or use manual mode");
          scenarioType = "manual";
        }
      }

      if (useCache) {
        const manifest = tileManifestRef.current;
        const tileDirs = tileDirectionsFromManifest(manifest);
        if (canUseTileMode(manifest, tilesReadyRef.current)) {
          const snapped = snapDirection(resolvedDir, tileDirs);
          if (requestId !== exposureRequestRef.current) return;
          setUseTileLayers(true);
          setTileDirection(snapped);
          setCacheDirection(snapped);
          setResults([]);
          setScenarioId(null);
          return;
        }
        setUseTileLayers(false);
        setTileDirection(null);
        try {
          const res = await getCachedExposure(
            currentArea.slug,
            resolvedDir,
            resolvedSpeed,
            resolvedGust,
          );
          if (requestId !== exposureRequestRef.current) return;
          setResults(res);
          setCacheDirection(res[0]?.cache_direction_deg ?? null);
          setScenarioId(null);
          return;
        } catch (e) {
          const msg = String(e);
          if (!msg.includes("404")) throw e;
        }
        if (requestId !== exposureRequestRef.current) return;
        setResults([]);
        setError(
          "Exposure cache miss for this wind — try another direction or wait for tiles",
        );
        return;
      }

      const scenario = await createScenario({
        area_slug: currentArea.slug,
        wind_speed_ms: resolvedSpeed,
        wind_direction_deg: resolvedDir,
        scenario_type: scenarioType,
      });
      if (requestId !== exposureRequestRef.current) return;

      setScenarioId(scenario.scenario_id);
      const res = await getScenarioResults(scenario.scenario_id);
      if (requestId !== exposureRequestRef.current) return;
      setResults(res);
      setCacheDirection(null);
    } catch (e) {
      if (requestId === exposureRequestRef.current) {
        setError(String(e));
      }
    } finally {
      if (requestId === exposureRequestRef.current) {
        setLoading(false);
      }
    }
  }, [applyWindIfCurrent, windGustMs]);

  useEffect(() => {
    if (mode !== "forecast") {
      forecastsRef.current = [];
      setForecastTimestamp(null);
    }
    if (mode !== "current") {
      weatherRefreshAtRef.current = 0;
    }
  }, [mode]);

  useEffect(() => {
    if (!area || !areaMetaReady || mode !== "manual") return;

    const manifest = tileManifestRef.current;
    const tileDirs = tileDirectionsFromManifest(manifest);
    if (useTileLayers && tileDirs.length > 0) {
      const snapped = snapDirection(direction, tileDirs);
      setTileDirection(snapped);
      setCacheDirection(snapped);
      return;
    }

    const timer = setTimeout(() => {
      void loadExposure("manual");
    }, 400);
    return () => clearTimeout(timer);
  }, [area, areaMetaReady, mode, direction, speed, useTileLayers, loadExposure]);

  useEffect(() => {
    if (!area || !areaMetaReady || mode !== "current") return;
    void loadExposure("current", 0, true);
  }, [area, areaMetaReady, mode, loadExposure]);

  useEffect(() => {
    if (!area || !areaMetaReady || mode !== "forecast") return;
    void loadExposure("forecast", forecastHour, false);
  }, [area, areaMetaReady, mode, forecastHour, loadExposure]);

  useEffect(() => {
    if (!area || mode !== "current") return;
    const timer = setInterval(() => {
      void loadExposure("current", 0, true);
    }, WEATHER_REFRESH_MS);
    return () => clearInterval(timer);
  }, [area, mode, loadExposure]);

  useEffect(() => {
    if (!area || !areaMetaReady || !cacheReady) return;
    void loadExposure(mode === "manual" ? "manual" : mode, forecastHour, false);
  }, [cacheReady, areaMetaReady]); // eslint-disable-line react-hooks/exhaustive-deps -- reload once when cache becomes ready

  const useFlowTileLayer = useTileLayers && flowTilesReady(tileManifest, tileDirection);

  useEffect(() => {
    if (!area || !cacheReady || !showFlowInterpretation || useFlowTileLayer) {
      setFlowIndicators([]);
      return;
    }
    let cancelled = false;
    void getFlowIndicators(area.slug, direction, speed, windGustMs)
      .then((rows) => { if (!cancelled) setFlowIndicators(rows); })
      .catch(() => { if (!cancelled) setFlowIndicators([]); });
    return () => { cancelled = true; };
  }, [area, cacheReady, showFlowInterpretation, direction, speed, windGustMs, useFlowTileLayer]);

  const vectorFieldAvailable = vectorZones.some((z) => z.vector_field_available);

  const handleRunValidation = async () => {
    if (!area) return;
    setValidationLoading(true);
    setError(null);
    try {
      await seedValidation(area.slug);
      const cases = await getValidationCases(area.id);
      const sanity = cases.find((c) => c.case_type === "manual_sanity") ?? cases[0];
      if (!sanity) throw new Error("No validation case");
      const result = await runValidation(sanity.id);
      setValidationMetrics({
        overall_accuracy: result.overall_accuracy,
        high_wind_recall: result.high_wind_recall,
        high_wind_precision: result.high_wind_precision ?? null,
        adjacent_class_accuracy: result.adjacent_class_accuracy ?? 0,
        metrics_json: result.metrics_json,
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setValidationLoading(false);
    }
  };

  const handleReport = async () => {
    if (!area || !selected) return;
    const desc = window.prompt("Describe the issue?");
    if (!desc) return;
    await submitFeedback({
      area_id: area.id,
      feature_id: selected.feature_id,
      feedback_type: "exposure_mismatch",
      description: desc,
      wind_direction_deg: direction,
    });
    alert("Feedback submitted — thank you.");
  };

  if (view === "accuracy") {
    return (
      <div className="page about">
        <nav>
          <button type="button" onClick={() => setView("map")}>← Map</button>
        </nav>
        <h1>About accuracy</h1>
        <p>
          Wind Track estimates <strong>street-level wind exposure</strong> from regional
          forecast wind and urban geometry. It is a screening tool, not engineering-grade CFD.
        </p>
        <ul>
          <li><strong>Estimated exposure</strong> — relative risk classes from geometry multipliers.</li>
          <li><strong>Approximate local wind</strong> — reference speed × local multiplier; not measured on-site.</li>
          <li><strong>Validated simulation</strong> — not provided in v0.5; vector zones may need advanced models.</li>
        </ul>
        <p>Weather from Open-Meteo is reference wind at 10 m, not street-level truth.</p>
        <p>Low confidence means uncertain estimate — not automatically low risk.</p>
        <p>Tunnel interiors and covered passages are not modeled.</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="top-bar">
        <h1>Wind Track</h1>
        <span className="subtitle">Lyon wind exposure beta</span>
        {areas.length > 1 && (
          <select
            className="area-select"
            value={area?.id ?? ""}
            onChange={(e) => {
              const next = areas.find((a) => a.id === Number(e.target.value));
              if (next) setArea(next);
            }}
          >
            {areas.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        )}
        <nav>
          <button type="button" onClick={() => setView(view === "quality" ? "map" : "quality")}>
            Data quality
          </button>
          <button
            type="button"
            onClick={() => setView(view === "validation" ? "map" : "validation")}
          >
            Validation
          </button>
          <button type="button" onClick={() => setView("accuracy")}>Accuracy</button>
        </nav>
        <p className="disclaimer">
          Screening estimate only — not certified pedestrian comfort or CFD.
        </p>
      </header>
      <aside className="sidebar">
        <WindControls
          mode={mode}
          direction={direction}
          speed={speed}
          forecastHour={forecastHour}
          forecastHours={forecastHours}
          forecastTimestamp={forecastTimestamp}
          loading={loading}
          cacheReady={cacheReady}
          cacheDirection={cacheDirection}
          onModeChange={setMode}
          onDirectionChange={setDirection}
          onSpeedChange={setSpeed}
          onForecastHourChange={setForecastHour}
        />
        <LayerMenu
          showConfidence={showConfidence}
          showSpecial={showSpecial}
          showGust={showGust}
          showBuildingExposure={showBuildingExposure}
          showFlowInterpretation={showFlowInterpretation}
          vectorFieldAvailable={vectorFieldAvailable}
          showVectorZones={showVectorZones}
          showLabels={showLabels}
          onToggleConfidence={() => setShowConfidence((v) => !v)}
          onToggleSpecial={() => setShowSpecial((v) => !v)}
          onToggleGust={() => setShowGust((v) => !v)}
          onToggleBuildingExposure={() => setShowBuildingExposure((v) => !v)}
          onToggleFlowInterpretation={() => setShowFlowInterpretation((v) => !v)}
          onToggleVectorZones={() => setShowVectorZones((v) => !v)}
          onToggleLabels={() => setShowLabels((v) => !v)}
        />
        <Legend showGust={showGust} />
        {needsImport && (
          <p className="import-warning">
            Synthetic test data only. Run <code>make import-osm</code> in terminal for real Lyon streets.
          </p>
        )}
        {error && <p className="error">{error}</p>}
      </aside>
      {view === "quality" && (
        <DataQualityPanel
          quality={quality}
          loading={qualityLoading}
          onClose={() => setView("map")}
        />
      )}
      {view === "validation" && (
        <ValidationPanel
          metrics={validationMetrics}
          loading={validationLoading}
          onRun={handleRunValidation}
          onClose={() => setView("map")}
        />
      )}
      {area && (
        <div className="map-wrap">
          <MapView
            center={[area.center_lon, area.center_lat]}
            zoom={area.default_zoom}
            areaSlug={area.slug}
            results={filterMapResults(results)}
            vectorZones={vectorZones}
            showConfidence={showConfidence}
            showSpecial={showSpecial}
            showGust={showGust}
            showBuildingExposure={showBuildingExposure}
            showFlowInterpretation={showFlowInterpretation}
            flowIndicators={flowIndicators}
            showVectorZones={showVectorZones}
            showLabels={showLabels}
            useTileLayers={useTileLayers}
            tileDirection={tileDirection}
            tileBaseReady={tileManifest?.base_pmtiles ?? false}
            flowTilesReady={useFlowTileLayer}
            selectedId={selected?.feature_id ?? null}
            onSelect={setSelected}
          />
          <WindFlowOverlay
            direction={direction}
            speed={speed}
            gustMs={windGustMs}
            cacheDirection={cacheDirection}
            visible={showFlowInterpretation}
          />
        </div>
      )}
      <ExplanationPanel
        feature={selected}
        windDirectionDeg={direction}
        onClose={() => setSelected(null)}
        onReport={handleReport}
      />
    </div>
  );
}