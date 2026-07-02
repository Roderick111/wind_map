import { useEffect, useRef } from "react";
import type maplibregl from "maplibre-gl";
import type { FlowPath } from "../api/schemas";
import {
  boundsOverlap,
  buildPathCache,
  buildViewportParticles,
  METEOR_MIN_ZOOM,
  meteorDrawStyle,
  normalizeStreakPixels,
  meteorOpacity,
  meteorSegment,
  meteorSpeedMps,
  type FlowParticle,
  type PathCache,
} from "../lib/flowPaths";

type Props = {
  map: maplibregl.Map | null;
  active: boolean;
  flowPaths: FlowPath[];
};

function mapReady(map: maplibregl.Map): boolean {
  try {
    return Boolean(map.isStyleLoaded()) && map.getContainer().clientWidth > 0;
  } catch {
    return false;
  }
}

function viewportFromMap(map: maplibregl.Map) {
  const bounds = map.getBounds();
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  };
}

export function StreetWindFlow({ map, active, flowPaths }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<FlowParticle[]>([]);
  const pathCacheRef = useRef<PathCache[]>([]);
  const pathsRef = useRef(flowPaths);
  const activeRef = useRef(active);
  const zoomRef = useRef(0);
  const rafRef = useRef(0);
  const lastTsRef = useRef(0);

  const rebuildParticles = (targetMap: maplibregl.Map) => {
    const zoom = targetMap.getZoom();
    if (zoom < METEOR_MIN_ZOOM) {
      particlesRef.current = [];
      return;
    }
    particlesRef.current = buildViewportParticles(
      pathsRef.current,
      pathCacheRef.current,
      viewportFromMap(targetMap),
      zoom,
    );
  };

  useEffect(() => {
    pathsRef.current = flowPaths;
    activeRef.current = active;
    pathCacheRef.current = buildPathCache(flowPaths);
    if (map) rebuildParticles(map);
    else particlesRef.current = [];
  }, [active, flowPaths, map]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!map || !canvas) return;

    const container = map.getContainer();
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const syncZoom = () => {
      zoomRef.current = map.getZoom();
    };

    const syncView = () => {
      syncZoom();
      rebuildParticles(map);
    };

    resize();
    syncView();
    map.on("resize", resize);
    map.on("zoom", syncZoom);
    map.on("zoomend", syncView);
    map.on("moveend", syncView);

    const draw = (ts: number) => {
      const rect = container.getBoundingClientRect();
      const zoom = map.getZoom();
      zoomRef.current = zoom;
      if (!activeRef.current || !mapReady(map) || zoom < METEOR_MIN_ZOOM) {
        ctx.clearRect(0, 0, rect.width, rect.height);
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const allPaths = pathsRef.current;
      if (particlesRef.current.length === 0) {
        ctx.clearRect(0, 0, rect.width, rect.height);
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const dt = lastTsRef.current ? Math.min(0.05, (ts - lastTsRef.current) / 1000) : 0.016;
      lastTsRef.current = ts;
      ctx.clearRect(0, 0, rect.width, rect.height);

      const viewport = viewportFromMap(map);
      const caches = pathCacheRef.current;
      const drawStyle = meteorDrawStyle(zoom);

      for (const particle of particlesRef.current) {
        const path = allPaths[particle.pathIndex];
        if (!path?.animate) continue;

        const cache = caches[particle.pathIndex];
        if (cache?.bounds && !boundsOverlap(
          cache.bounds,
          viewport.west,
          viewport.south,
          viewport.east,
          viewport.north,
        )) {
          continue;
        }

        const total = cache?.totalM ?? path.length_m;
        if (total <= 0) continue;

        particle.progress += (meteorSpeedMps(path) * dt) / total;
        if (particle.progress >= 1) particle.progress -= 1;

        const segment = meteorSegment(path, particle.progress);
        if (!segment) continue;

        const headPx = map.project([segment.head.lng, segment.head.lat]);
        const tailPx = normalizeStreakPixels(
          headPx,
          map.project([segment.tail.lng, segment.tail.lat]),
          drawStyle,
          particle.phase,
        );

        if (
          !Number.isFinite(headPx.x)
          || !Number.isFinite(headPx.y)
          || headPx.x < -24
          || headPx.y < -24
          || headPx.x > rect.width + 24
          || headPx.y > rect.height + 24
        ) {
          continue;
        }

        const shimmer = 0.92 + 0.08 * Math.sin(ts * 0.004 + particle.phase * 6.28);
        const alpha = Math.min(1, meteorOpacity(path) * shimmer);
        const grad = ctx.createLinearGradient(tailPx.x, tailPx.y, headPx.x, headPx.y);
        grad.addColorStop(0, "rgba(230, 245, 255, 0)");
        grad.addColorStop(0.35, `rgba(230, 245, 255, ${alpha * 0.25})`);
        grad.addColorStop(0.75, `rgba(248, 252, 255, ${alpha * 0.75})`);
        grad.addColorStop(1, `rgba(255, 255, 255, ${alpha})`);

        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(tailPx.x, tailPx.y);
        ctx.lineTo(headPx.x, headPx.y);

        ctx.strokeStyle = `rgba(186, 220, 255, ${alpha * 0.4})`;
        ctx.lineWidth = drawStyle.lineWidth + drawStyle.haloWidth;
        ctx.stroke();

        ctx.strokeStyle = grad;
        ctx.lineWidth = drawStyle.lineWidth;
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      lastTsRef.current = 0;
      map.off("resize", resize);
      map.off("zoom", syncZoom);
      map.off("zoomend", syncView);
      map.off("moveend", syncView);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [map, flowPaths, active]);

  if (!active || flowPaths.length === 0) return null;

  return <canvas ref={canvasRef} className="street-wind-canvas" aria-hidden />;
}