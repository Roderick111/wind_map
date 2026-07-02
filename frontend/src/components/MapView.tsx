import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureResult, FlowPath } from "../api/schemas";
import { flowPathsToGeoJSON } from "../lib/flowPaths";
import { confidenceOpacity, riskScoreColor } from "../lib/exposure";
import { ensurePmtilesProtocol, EXPOSURE_COLOR_EXPR, pmtilesUrl } from "../lib/pmtiles";
import type { MapViewMode } from "./LayerMenu";
import { StreetWindFlow } from "./StreetWindFlow";

type Props = {
  center: [number, number];
  zoom: number;
  areaSlug: string | null;
  results: FeatureResult[];
  mapViewMode: MapViewMode;
  flowPaths: FlowPath[];
  showLabels: boolean;
  useTileLayers: boolean;
  tileDirection: number | null;
  tileBaseReady: boolean;
  selectedId: number | null;
  onSelect: (feature: FeatureResult) => void;
};

const GEOJSON_EXPOSURE_LAYERS = [
  "exposure-fill", "exposure-line", "exposure-point",
];
const GEOJSON_LABEL_LAYERS = ["exposure-labels", "exposure-labels-poly"];
const EXPOSURE_TILE_FILL_LAYERS = ["exposure-pmtiles-fill"];
const EXPOSURE_TILE_LINE_LAYERS = ["exposure-pmtiles-line"];
const FLOW_PATH_LAYERS = ["flow-path-line"];

function featureLabel(r: FeatureResult): string {
  const name = r.name?.trim();
  const hasRealName = name && !name.startsWith("way/") && !name.startsWith("relation/");
  if (hasRealName) return name;
  const defaults: Record<string, string> = {
    bridge: "Bridge",
    quay: "Quay",
    river: "River",
    open_space: "Square",
    park: "Park",
    tunnel: "Tunnel",
  };
  return defaults[r.feature_type] ?? "";
}

function featureFromTileProps(
  f: maplibregl.MapGeoJSONFeature,
): FeatureResult | null {
  const p = f.properties;
  if (!p?.feature_id) return null;
  return {
    feature_id: Number(p.feature_id),
    feature_type: String(p.feature_type ?? "street_segment"),
    name: p.name ? String(p.name) : null,
    geom: f.geometry as unknown as FeatureResult["geom"],
    risk_score: Number(p.risk_score ?? 0),
    exposure_class: String(p.exposure_class ?? "low"),
    local_multiplier: 1,
    approx_local_speed_ms: null,
    gust_sensitive: Boolean(p.gust_sensitive),
    confidence: Number(p.confidence ?? 0.7),
    handling_mode: String(p.handling_mode ?? "normal_score"),
    subscores: {},
    cause_tags: [],
    mitigation_tags: [],
    model_note: null,
    limitations: [],
    cache_hit: true,
    cache_direction_deg: p.direction_deg != null ? Number(p.direction_deg) : null,
  };
}

function resultsToGeoJSON(
  results: FeatureResult[],
  showLabels: boolean,
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: results
      .filter((r) => r.handling_mode !== "excluded")
      .map((r) => ({
        type: "Feature",
        id: r.feature_id,
        geometry: r.geom as unknown as GeoJSON.Geometry,
        properties: {
          feature_id: r.feature_id,
          exposure_class: r.exposure_class,
          risk_score: r.risk_score,
          color: riskScoreColor(r.risk_score),
          opacity: confidenceOpacity(r.confidence),
          handling_mode: r.handling_mode,
          name: r.name,
          label: showLabels ? featureLabel(r) : "",
          feature_type: r.feature_type,
        },
      })),
  };
}

function setLayerVisibility(map: maplibregl.Map, ids: string[], visible: boolean) {
  for (const id of ids) {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }
}

function buildOpacityExpr(
  showConfidence: boolean,
): maplibregl.ExpressionSpecification {
  return showConfidence
    ? ["+", 0.35, ["*", ["get", "confidence"], 0.65]]
    : ["literal", 0.85];
}

function buildColorExpr(showGust: boolean): maplibregl.ExpressionSpecification {
  return showGust
    ? ["case", ["get", "gust_sensitive"], "#c026d3", EXPOSURE_COLOR_EXPR]
    : EXPOSURE_COLOR_EXPR;
}

/** Polygon types worth drawing as fills at city scale (exclude park/vegetation/river meshes). */
const STREET_SCALE_POLYGON_TYPES = ["open_space", "quay", "bridge"];

function buildPolygonFilter(
  showBuildingExposure: boolean,
): maplibregl.FilterSpecification {
  if (showBuildingExposure) {
    return ["==", ["geometry-type"], "Polygon"];
  }
  return [
    "all",
    ["==", ["geometry-type"], "Polygon"],
    ["in", ["get", "feature_type"], ["literal", [...STREET_SCALE_POLYGON_TYPES]]],
  ];
}

function removeExposureTileLayers(map: maplibregl.Map) {
  for (const id of [...EXPOSURE_TILE_FILL_LAYERS, ...EXPOSURE_TILE_LINE_LAYERS]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource("exposure-pmtiles")) map.removeSource("exposure-pmtiles");
}

function removeAllPmtiles(map: maplibregl.Map) {
  removeExposureTileLayers(map);
  if (map.getLayer("base-tiles-line")) map.removeLayer("base-tiles-line");
  if (map.getSource("base-tiles")) map.removeSource("base-tiles");
}

export function MapView({
  center,
  zoom,
  areaSlug,
  results,
  mapViewMode,
  flowPaths,
  showLabels,
  useTileLayers,
  tileDirection,
  tileBaseReady,
  selectedId,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);
  const mapViewModeRef = useRef(mapViewMode);
  mapViewModeRef.current = mapViewMode;
  const flowPathsRef = useRef(flowPaths);
  flowPathsRef.current = flowPaths;
  const resultsRef = useRef(results);
  const onSelectRef = useRef(onSelect);
  const tileClickRef = useRef<(
    e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] },
  ) => void | null>(null);
  const exposureDirRef = useRef<number | null>(null);
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const styleWaitBoundRef = useRef(false);
  const performSyncTileModeRef = useRef<(map: maplibregl.Map) => void>(() => {});
  const applyExposureDataRef = useRef<(map: maplibregl.Map) => void>(() => {});
  const applyMapViewModeRef = useRef<(map: maplibregl.Map) => void>(() => {});
  const applyFlowPathDataRef = useRef<(map: maplibregl.Map) => void>(() => {});
  resultsRef.current = results;
  onSelectRef.current = onSelect;

  const flushMapState = useCallback((map: maplibregl.Map) => {
    applyExposureDataRef.current(map);
    applyFlowPathDataRef.current(map);
    performSyncTileModeRef.current(map);
    applyMapViewModeRef.current(map);
  }, []);

  const runWhenMapReady = useCallback((fn: () => void) => {
    const map = mapRef.current;
    if (!map) return;
    if (map.isStyleLoaded()) {
      fn();
      return;
    }
    if (styleWaitBoundRef.current) return;
    styleWaitBoundRef.current = true;
    map.once("load", () => {
      styleWaitBoundRef.current = false;
      if (mapRef.current === map) flushMapState(map);
    });
  }, [flushMapState]);

  const bindTileClickHandlers = useCallback((map: maplibregl.Map) => {
    if (tileClickRef.current) {
      map.off("click", "exposure-pmtiles-fill", tileClickRef.current);
      map.off("click", "exposure-pmtiles-line", tileClickRef.current);
    }
    const handler = (
      e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] },
    ) => {
      const raw = e.features?.[0];
      if (!raw) return;
      const feat = featureFromTileProps(raw);
      if (feat) onSelectRef.current(feat);
    };
    tileClickRef.current = handler;
    map.on("click", "exposure-pmtiles-fill", handler);
    map.on("click", "exposure-pmtiles-line", handler);
  }, []);

  const applyExposureTileStyle = useCallback((map: maplibregl.Map) => {
    const opacityExpr = buildOpacityExpr(true);
    const colorExpr = buildColorExpr(false);
    const polygonFilter = buildPolygonFilter(false);

    if (map.getLayer("exposure-pmtiles-fill")) {
      map.setFilter("exposure-pmtiles-fill", polygonFilter);
      map.setPaintProperty("exposure-pmtiles-fill", "fill-color", colorExpr);
      map.setPaintProperty("exposure-pmtiles-fill", "fill-opacity", opacityExpr);
    }
    if (map.getLayer("exposure-pmtiles-line")) {
      map.setPaintProperty("exposure-pmtiles-line", "line-color", colorExpr);
      map.setPaintProperty("exposure-pmtiles-line", "line-width", 5);
      map.setPaintProperty("exposure-pmtiles-line", "line-opacity", opacityExpr);
    }
  }, []);

  const addExposureTileLayers = useCallback((
    map: maplibregl.Map,
    slug: string,
    direction: number,
  ) => {
    ensurePmtilesProtocol();
    map.addSource("exposure-pmtiles", {
      type: "vector",
      url: pmtilesUrl(slug, `exposure_${direction}.pmtiles`),
    });

    const opacityExpr = buildOpacityExpr(true);
    const colorExpr = buildColorExpr(false);
    const polygonFilter = buildPolygonFilter(false);

    map.addLayer({
      id: "exposure-pmtiles-fill",
      type: "fill",
      source: "exposure-pmtiles",
      "source-layer": "exposure",
      filter: polygonFilter,
      paint: {
        "fill-color": colorExpr,
        "fill-opacity": opacityExpr,
      },
    });
    map.addLayer({
      id: "exposure-pmtiles-line",
      type: "line",
      source: "exposure-pmtiles",
      "source-layer": "exposure",
      filter: ["==", ["geometry-type"], "LineString"],
      paint: {
        "line-color": colorExpr,
        "line-width": 5,
        "line-opacity": opacityExpr,
      },
    });
    bindTileClickHandlers(map);
    exposureDirRef.current = direction;
  }, [bindTileClickHandlers]);

  const ensureBaseTileLayer = useCallback((map: maplibregl.Map, slug: string) => {
    if (map.getSource("base-tiles")) return;
    ensurePmtilesProtocol();
    map.addSource("base-tiles", {
      type: "vector",
      url: pmtilesUrl(slug, "base.pmtiles"),
    });
    map.addLayer({
      id: "base-tiles-line",
      type: "line",
      source: "base-tiles",
      "source-layer": "base",
      filter: ["!=", ["get", "feature_type"], "building"],
      paint: {
        "line-color": "#64748b",
        "line-width": 1,
        "line-opacity": 0.35,
      },
    });
  }, []);

  const applyMapViewMode = useCallback((map: maplibregl.Map) => {
    const mode = mapViewModeRef.current;
    const exposureOn = mode === "exposure";
    const flowOn = mode === "flow";
    const hasFlowPaths = flowPathsRef.current.length > 0;
    const showExposureLines = !flowOn || !hasFlowPaths;

    setLayerVisibility(
      map,
      GEOJSON_EXPOSURE_LAYERS.filter((id) => id !== "exposure-line"),
      !useTileLayers && (exposureOn || (flowOn && !hasFlowPaths)),
    );
    setLayerVisibility(map, ["exposure-line"], !useTileLayers && showExposureLines && (exposureOn || flowOn));
    setLayerVisibility(map, GEOJSON_LABEL_LAYERS, showLabels && (exposureOn || flowOn));
    setLayerVisibility(map, EXPOSURE_TILE_FILL_LAYERS, useTileLayers && exposureOn);
    setLayerVisibility(map, EXPOSURE_TILE_LINE_LAYERS, useTileLayers && showExposureLines && (exposureOn || flowOn));
    setLayerVisibility(map, FLOW_PATH_LAYERS, false);

    if (map.getLayer("exposure-line")) {
      map.setPaintProperty(
        "exposure-line",
        "line-opacity",
        flowOn && !exposureOn ? 0.14 : ["get", "opacity"],
      );
      map.setPaintProperty(
        "exposure-line",
        "line-color",
        flowOn && !exposureOn ? "#475569" : ["get", "color"],
      );
      map.setPaintProperty("exposure-line", "line-width", flowOn && !exposureOn ? 1.5 : 5);
    }
    if (map.getLayer("exposure-fill")) {
      map.setLayoutProperty("exposure-fill", "visibility", exposureOn ? "visible" : "none");
    }
    if (map.getLayer("exposure-pmtiles-line")) {
      map.setPaintProperty(
        "exposure-pmtiles-line",
        "line-opacity",
        flowOn && !exposureOn ? 0.16 : buildOpacityExpr(true),
      );
      map.setPaintProperty(
        "exposure-pmtiles-line",
        "line-color",
        flowOn && !exposureOn ? "#475569" : buildColorExpr(false),
      );
      map.setPaintProperty("exposure-pmtiles-line", "line-width", flowOn && !exposureOn ? 1.5 : 5);
    }
  }, [showLabels, useTileLayers]);

  const performSyncTileMode = useCallback((map: maplibregl.Map) => {
    if (!areaSlug) return;
    const mode = mapViewModeRef.current;
    const needsTiles = mode !== "base";

    if (!useTileLayers || tileDirection == null || !needsTiles) {
      removeAllPmtiles(map);
      exposureDirRef.current = null;
      applyMapViewModeRef.current(map);
      applyFlowPathDataRef.current(map);
      return;
    }

    setLayerVisibility(map, [...GEOJSON_EXPOSURE_LAYERS, ...GEOJSON_LABEL_LAYERS], false);

    if (tileBaseReady) {
      ensureBaseTileLayer(map, areaSlug);
    } else if (map.getSource("base-tiles")) {
      if (map.getLayer("base-tiles-line")) map.removeLayer("base-tiles-line");
      map.removeSource("base-tiles");
    }

    const dirChanged = exposureDirRef.current !== tileDirection;
    const hasExposureLayers = Boolean(map.getLayer("exposure-pmtiles-fill"));
    const needsExposure = !map.getSource("exposure-pmtiles") || dirChanged || !hasExposureLayers;
    if (needsExposure) {
      removeExposureTileLayers(map);
      addExposureTileLayers(map, areaSlug, tileDirection);
    } else {
      applyExposureTileStyle(map);
    }

    applyMapViewModeRef.current(map);
    applyFlowPathDataRef.current(map);
  }, [
    addExposureTileLayers,
    applyExposureTileStyle,
    areaSlug,
    ensureBaseTileLayer,
    tileBaseReady,
    tileDirection,
    useTileLayers,
  ]);

  const applyExposureData = useCallback((map: maplibregl.Map) => {
    const src = map.getSource("exposure") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData(resultsToGeoJSON(resultsRef.current, showLabels));
  }, [showLabels]);

  const applyFlowPathData = useCallback((map: maplibregl.Map) => {
    const src = map.getSource("flow-paths") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData(flowPathsToGeoJSON(flowPathsRef.current));
    applyMapViewModeRef.current(map);
    if (map.getLayer("flow-path-line") && flowPathsRef.current.length > 0) {
      map.moveLayer("flow-path-line");
    }
  }, []);

  performSyncTileModeRef.current = performSyncTileMode;
  applyExposureDataRef.current = applyExposureData;
  applyMapViewModeRef.current = applyMapViewMode;
  applyFlowPathDataRef.current = applyFlowPathData;

  const syncTileMode = useCallback(() => {
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (!map) return;
      performSyncTileMode(map);
    });
  }, [performSyncTileMode, runWhenMapReady]);

  const applyExposure = useCallback(() => {
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (!map) return;
      applyExposureData(map);
    });
  }, [applyExposureData, runWhenMapReady]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center,
      zoom,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const clickHandler = (
      e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] },
    ) => {
      const fid = e.features?.[0]?.properties?.feature_id;
      if (fid == null) return;
      const feat = resultsRef.current.find((r) => r.feature_id === Number(fid));
      if (feat) onSelectRef.current(feat);
    };

    map.on("load", () => {
      map.addSource("exposure", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "exposure-fill",
        type: "fill",
        source: "exposure",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": ["get", "opacity"],
        },
      });
      map.addLayer({
        id: "exposure-line",
        type: "line",
        source: "exposure",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": ["get", "color"],
          "line-width": 5,
          "line-opacity": ["get", "opacity"],
        },
      });
      map.addLayer({
        id: "exposure-point",
        type: "circle",
        source: "exposure",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": 8,
          "circle-opacity": ["get", "opacity"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#0f172a",
        },
      });
      map.addLayer({
        id: "exposure-labels",
        type: "symbol",
        source: "exposure",
        filter: ["all", ["!=", ["get", "label"], ""], ["==", ["geometry-type"], "LineString"]],
        layout: {
          "text-field": ["get", "label"],
          "text-size": 11,
          "symbol-placement": "line",
          "text-rotation-alignment": "map",
        },
        paint: {
          "text-color": "#f8fafc",
          "text-halo-color": "#0f172a",
          "text-halo-width": 1.2,
        },
      });
      map.addSource("flow-paths", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "flow-path-line",
        type: "line",
        source: "flow-paths",
        layout: { visibility: "none" },
        paint: {
          "line-color": "#60a5fa",
          "line-width": 1.4,
          "line-opacity": 0.28,
        },
      });
      map.addLayer({
        id: "exposure-labels-poly",
        type: "symbol",
        source: "exposure",
        filter: ["all", ["!=", ["get", "label"], ""], ["==", ["geometry-type"], "Polygon"]],
        layout: {
          "text-field": ["get", "label"],
          "text-size": 11,
        },
        paint: {
          "text-color": "#f8fafc",
          "text-halo-color": "#0f172a",
          "text-halo-width": 1.2,
        },
      });
      map.on("click", "exposure-fill", clickHandler);
      map.on("click", "exposure-line", clickHandler);
      map.on("click", "exposure-point", clickHandler);

      flushMapState(map);
    });

    mapRef.current = map;
    setMapInstance(map);
    return () => {
      setMapInstance(null);
      styleWaitBoundRef.current = false;
      map.remove();
      mapRef.current = null;
      exposureDirRef.current = null;
      tileClickRef.current = null;
    };
  }, [center, zoom, flushMapState]);

  useEffect(() => {
    applyExposure();
  }, [results, applyExposure]);

  useEffect(() => {
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (map) applyFlowPathData(map);
    });
  }, [applyFlowPathData, flowPaths, runWhenMapReady]);

  useEffect(() => {
    syncTileMode();
  }, [syncTileMode]);

  useEffect(() => {
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (map) applyMapViewMode(map);
    });
  }, [applyMapViewMode, mapViewMode, runWhenMapReady, showLabels]);

  useEffect(() => {
    const map = mapInstance;
    if (!map) return;
    const onViewChange = () => applyMapViewMode(map);
    map.on("zoom", onViewChange);
    map.on("move", onViewChange);
    return () => {
      map.off("zoom", onViewChange);
      map.off("move", onViewChange);
    };
  }, [applyMapViewMode, mapInstance]);

  useEffect(() => {
    if (selectedId == null) return;
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (!map) return;
      const feat = results.find((r) => r.feature_id === selectedId);
      if (!feat) return;
      const coords = centroidOf(feat.geom as unknown as GeoJSON.Geometry);
      map.flyTo({ center: coords, zoom: Math.max(map.getZoom(), 16), duration: 600 });
    });
  }, [runWhenMapReady, selectedId, results]);

  return (
    <div className="map-stack">
      <div ref={containerRef} className="map-container" />
      <StreetWindFlow
        map={mapInstance}
        active={mapViewMode === "flow"}
        flowPaths={flowPaths}
      />
    </div>
  );
}

function centroidOf(geom: GeoJSON.Geometry): [number, number] {
  if (geom.type === "Point") return [geom.coordinates[0], geom.coordinates[1]];
  if (geom.type === "LineString") {
    const mid = geom.coordinates[Math.floor(geom.coordinates.length / 2)];
    return [mid[0], mid[1]];
  }
  if (geom.type === "Polygon") {
    const ring = geom.coordinates[0];
    const lon = ring.reduce((s: number, c: number[]) => s + c[0], 0) / ring.length;
    const lat = ring.reduce((s: number, c: number[]) => s + c[1], 0) / ring.length;
    return [lon, lat];
  }
  return [4.8357, 45.764];
}