import { useCallback, useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureResult } from "../api/schemas";
import { confidenceOpacity, exposureColor } from "../lib/exposure";
import { ensurePmtilesProtocol, EXPOSURE_COLOR_EXPR, pmtilesUrl } from "../lib/pmtiles";

type VectorZone = {
  id: number;
  name: string;
  zone_type: string;
  status: string;
  boundary: GeoJSON.Geometry;
};

type Props = {
  center: [number, number];
  zoom: number;
  areaSlug: string | null;
  results: FeatureResult[];
  vectorZones: VectorZone[];
  showConfidence: boolean;
  showSpecial: boolean;
  showGust: boolean;
  showBuildingExposure: boolean;
  showVectorZones: boolean;
  showLabels: boolean;
  useTileLayers: boolean;
  tileDirection: number | null;
  tileBaseReady: boolean;
  selectedId: number | null;
  onSelect: (feature: FeatureResult) => void;
};

const GEOJSON_LAYERS = [
  "exposure-fill", "exposure-line", "exposure-point", "exposure-labels", "exposure-labels-poly",
];
const EXPOSURE_TILE_LAYERS = ["exposure-pmtiles-fill", "exposure-pmtiles-line"];

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
  showConfidence: boolean,
  showSpecial: boolean,
  showGust: boolean,
  showLabels: boolean,
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: results
      .filter((r) => {
        if (r.handling_mode === "excluded") return showSpecial;
        return true;
      })
      .map((r) => ({
        type: "Feature",
        id: r.feature_id,
        geometry: r.geom as unknown as GeoJSON.Geometry,
        properties: {
          feature_id: r.feature_id,
          exposure_class: r.exposure_class,
          risk_score: r.risk_score,
          color: showGust && r.gust_sensitive ? "#c026d3" : exposureColor(r.exposure_class),
          opacity: showConfidence ? confidenceOpacity(r.confidence) : 0.85,
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

function buildPolygonFilter(
  showBuildingExposure: boolean,
): maplibregl.FilterSpecification {
  if (showBuildingExposure) {
    return ["==", ["geometry-type"], "Polygon"];
  }
  return [
    "all",
    ["==", ["geometry-type"], "Polygon"],
    ["!=", ["get", "feature_type"], "building"],
  ];
}

function removeExposureTileLayers(map: maplibregl.Map) {
  for (const id of EXPOSURE_TILE_LAYERS) {
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
  vectorZones,
  showConfidence,
  showSpecial,
  showGust,
  showBuildingExposure,
  showVectorZones,
  showLabels,
  useTileLayers,
  tileDirection,
  tileBaseReady,
  selectedId,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const resultsRef = useRef(results);
  const onSelectRef = useRef(onSelect);
  const tileClickRef = useRef<(
    e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] },
  ) => void | null>(null);
  const exposureDirRef = useRef<number | null>(null);
  const styleWaitBoundRef = useRef(false);
  const performSyncTileModeRef = useRef<(map: maplibregl.Map) => void>(() => {});
  const applyExposureDataRef = useRef<(map: maplibregl.Map) => void>(() => {});
  const applyVectorZonesDataRef = useRef<(map: maplibregl.Map) => void>(() => {});
  resultsRef.current = results;
  onSelectRef.current = onSelect;

  const flushMapState = useCallback((map: maplibregl.Map) => {
    applyExposureDataRef.current(map);
    applyVectorZonesDataRef.current(map);
    performSyncTileModeRef.current(map);
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

  const applyExposureTileStyle = useCallback((
    map: maplibregl.Map,
    confidence: boolean,
    gust: boolean,
    buildings: boolean,
  ) => {
    const opacityExpr = buildOpacityExpr(confidence);
    const colorExpr = buildColorExpr(gust);
    const polygonFilter = buildPolygonFilter(buildings);

    if (map.getLayer("exposure-pmtiles-fill")) {
      map.setFilter("exposure-pmtiles-fill", polygonFilter);
      map.setPaintProperty("exposure-pmtiles-fill", "fill-color", colorExpr);
      map.setPaintProperty("exposure-pmtiles-fill", "fill-opacity", opacityExpr);
    }
    if (map.getLayer("exposure-pmtiles-line")) {
      map.setPaintProperty("exposure-pmtiles-line", "line-color", colorExpr);
      map.setPaintProperty("exposure-pmtiles-line", "line-opacity", opacityExpr);
    }
  }, []);

  const addExposureTileLayers = useCallback((
    map: maplibregl.Map,
    slug: string,
    direction: number,
    confidence: boolean,
    gust: boolean,
    buildings: boolean,
  ) => {
    ensurePmtilesProtocol();
    map.addSource("exposure-pmtiles", {
      type: "vector",
      url: pmtilesUrl(slug, `exposure_${direction}.pmtiles`),
    });

    const opacityExpr = buildOpacityExpr(confidence);
    const colorExpr = buildColorExpr(gust);
    const polygonFilter = buildPolygonFilter(buildings);

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

  const performSyncTileMode = useCallback((map: maplibregl.Map) => {
    if (!areaSlug) return;

    if (!useTileLayers || tileDirection == null) {
      removeAllPmtiles(map);
      exposureDirRef.current = null;
      setLayerVisibility(map, GEOJSON_LAYERS, true);
      return;
    }

    setLayerVisibility(map, GEOJSON_LAYERS, false);

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
      addExposureTileLayers(
        map,
        areaSlug,
        tileDirection,
        showConfidence,
        showGust,
        showBuildingExposure,
      );
      return;
    }

    applyExposureTileStyle(map, showConfidence, showGust, showBuildingExposure);
  }, [
    addExposureTileLayers,
    applyExposureTileStyle,
    areaSlug,
    ensureBaseTileLayer,
    showBuildingExposure,
    showConfidence,
    showGust,
    tileBaseReady,
    tileDirection,
    useTileLayers,
  ]);

  const applyExposureData = useCallback((map: maplibregl.Map) => {
    const src = map.getSource("exposure") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData(
      resultsToGeoJSON(resultsRef.current, showConfidence, showSpecial, showGust, showLabels),
    );
  }, [showConfidence, showSpecial, showGust, showLabels]);

  const applyVectorZonesData = useCallback((map: maplibregl.Map) => {
    const src = map.getSource("vector-zones") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    if (!showVectorZones) {
      src.setData({ type: "FeatureCollection", features: [] });
      return;
    }
    src.setData({
      type: "FeatureCollection",
      features: vectorZones.map((z) => ({
        type: "Feature",
        geometry: z.boundary,
        properties: { name: z.name, status: z.status },
      })),
    });
  }, [vectorZones, showVectorZones]);

  performSyncTileModeRef.current = performSyncTileMode;
  applyExposureDataRef.current = applyExposureData;
  applyVectorZonesDataRef.current = applyVectorZonesData;

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

  const applyVectorZones = useCallback(() => {
    runWhenMapReady(() => {
      const map = mapRef.current;
      if (!map) return;
      applyVectorZonesData(map);
    });
  }, [applyVectorZonesData, runWhenMapReady]);

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
      map.addSource("vector-zones", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "vector-zones-line",
        type: "line",
        source: "vector-zones",
        paint: {
          "line-color": "#6366f1",
          "line-width": 2,
          "line-dasharray": [4, 2],
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
    return () => {
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
    applyVectorZones();
  }, [applyVectorZones]);

  useEffect(() => {
    syncTileMode();
  }, [syncTileMode]);

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

  return <div ref={containerRef} className="map-container" />;
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