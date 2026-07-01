import { useEffect, useRef } from "react";
import type maplibregl from "maplibre-gl";
import type { FlowIndicator } from "../api/schemas";
import { exposureColor } from "../lib/exposure";

type Props = {
  map: maplibregl.Map | null;
  active: boolean;
  windDirectionDeg: number;
  flowIndicators: FlowIndicator[];
  dimExposure: boolean;
};

type Particle = {
  x: number;
  y: number;
  speed: number;
  len: number;
  color: string;
  angle: number;
};

function spawnParticles(
  width: number,
  height: number,
  indicators: FlowIndicator[],
  fallbackDir: number,
): Particle[] {
  if (indicators.length > 0) {
    return indicators.slice(0, 220).map((ind) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      speed: 0.6 + ind.flow_strength * 0.9,
      len: 10 + ind.flow_strength * 14,
      color: exposureColor(ind.exposure_class),
      angle: (ind.flow_direction_deg * Math.PI) / 180,
    }));
  }
  const angle = (fallbackDir * Math.PI) / 180;
  return Array.from({ length: 90 }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    speed: 0.8 + Math.random() * 0.6,
    len: 12 + Math.random() * 10,
    color: "rgba(148, 163, 184, 0.75)",
    angle,
  }));
}

export function FlowAnimationCanvas({
  map,
  active,
  windDirectionDeg,
  flowIndicators,
  dimExposure,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number>(0);
  const indicatorsRef = useRef(flowIndicators);
  const dirRef = useRef(windDirectionDeg);
  indicatorsRef.current = flowIndicators;
  dirRef.current = windDirectionDeg;

  useEffect(() => {
    if (!active || !map || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const rect = map.getContainer().getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      particlesRef.current = spawnParticles(
        canvas.width,
        canvas.height,
        indicatorsRef.current,
        dirRef.current,
      );
    };

    resize();
    map.on("resize", resize);
    map.on("move", resize);

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (dimExposure) {
        ctx.fillStyle = "rgba(15, 23, 42, 0.12)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      const projected: { x: number; y: number; p: Particle }[] = [];
      if (indicatorsRef.current.length > 0) {
        for (const ind of indicatorsRef.current.slice(0, 220)) {
          const coords = (ind.geom as { coordinates?: [number, number] }).coordinates;
          if (!coords) continue;
          const pt = map.project(coords);
          projected.push({
            x: pt.x,
            y: pt.y,
            p: {
              x: pt.x,
              y: pt.y,
              speed: 0.6 + ind.flow_strength * 0.9,
              len: 10 + ind.flow_strength * 14,
              color: exposureColor(ind.exposure_class),
              angle: (ind.flow_direction_deg * Math.PI) / 180,
            },
          });
        }
      }

      const pool = projected.length > 0
        ? projected.map((row) => row.p)
        : particlesRef.current;

      const t = performance.now() / 1000;
      for (let i = 0; i < pool.length; i += 1) {
        const p = pool[i];
        const drift = (t * p.speed * 18 + i * 7) % 48;
        const x = p.x + Math.sin(p.angle) * drift;
        const y = p.y - Math.cos(p.angle) * drift;
        const x2 = x + Math.sin(p.angle) * p.len;
        const y2 = y - Math.cos(p.angle) * p.len;

        ctx.strokeStyle = p.color;
        ctx.globalAlpha = 0.55 + 0.35 * Math.sin(t * 2 + i);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      map.off("resize", resize);
      map.off("move", resize);
    };
  }, [active, dimExposure, map]);

  useEffect(() => {
    if (!active || !map || !canvasRef.current) return;
    const canvas = canvasRef.current;
    particlesRef.current = spawnParticles(
      canvas.width,
      canvas.height,
      flowIndicators,
      windDirectionDeg,
    );
  }, [active, flowIndicators, map, windDirectionDeg]);

  if (!active) return null;

  return <canvas ref={canvasRef} className="flow-animation-canvas" aria-hidden />;
}