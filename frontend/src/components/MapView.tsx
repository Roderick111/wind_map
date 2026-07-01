import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { FeatureResult } from "../api/schemas";
import { confidenceOpacity, exposureColor } from "../lib/exposure";

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
  results: FeatureResult[];
  vectorZones: VectorZone[];
  showConfidence: boolean;
  showSpecial: boolean;
  showGust: boolean;
  showVectorZones: boolean;
  showLabels: boolean;
  selectedId: number | null;
  onSelect: (feature: FeatureResult) => void;
};

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

export function MapView({
  center,
  zoom,
  results,
  vectorZones,
  showConfidence,
  showSpecial,
  showGust,
  showVectorZones,
  showLabels,
  selectedId,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const resultsRef = useRef(results);
  resultsRef.current = results;
  const [mapReady, setMapReady] = useState(false);

  const applyExposure = useCallback(() => {
    const map = mapRef.current;
    const src = map?.getSource("exposure") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    src.setData(
      resultsToGeoJSON(resultsRef.current, showConfidence, showSpecial, showGust, showLabels),
    );
  }, [showConfidence, showSpecial, showGust, showLabels]);

  const applyVectorZones = useCallback(() => {
    const map = mapRef.current;
    const src = map?.getSource("vector-zones") as maplibregl.GeoJSONSource | undefined;
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
      if (feat) onSelect(feat);
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
      setMapReady(true);
    });

    mapRef.current = map;
    return () => {
      setMapReady(false);
      map.remove();
      mapRef.current = null;
    };
  }, [center, zoom, onSelect]);

  useEffect(() => {
    if (!mapReady) return;
    applyExposure();
  }, [mapReady, results, applyExposure]);

  useEffect(() => {
    if (!mapReady) return;
    applyVectorZones();
  }, [mapReady, applyVectorZones]);

  useEffect(() => {
    if (!mapReady || selectedId == null) return;
    const map = mapRef.current;
    if (!map) return;
    const feat = results.find((r) => r.feature_id === selectedId);
    if (!feat) return;
    const coords = centroidOf(feat.geom as unknown as GeoJSON.Geometry);
    map.flyTo({ center: coords, zoom: Math.max(map.getZoom(), 16), duration: 600 });
  }, [mapReady, selectedId, results]);

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