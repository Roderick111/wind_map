import {
  AreaSchema,
  DataQualitySchema,
  TileManifestSchema,
  FeatureResultSchema,
  ScenarioSchema,
  WeatherSchema,
} from "./schemas";
import { normalizeDirectionDeg } from "../lib/wind";
import type { Area, DataQuality, FeatureResult, Scenario, TileManifest, Weather } from "./schemas";

const BASE = "/api";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export async function getAreaSummary(areaId: number): Promise<{
  area_id: number;
  feature_count: number;
  street_count: number;
  source_type: string;
  needs_osm_import: boolean;
  data_version: string | null;
  cache_ready: boolean;
  cache_entries: number;
  tiles_ready?: boolean;
  direction_count?: number;
}> {
  return fetchJson(`${BASE}/areas/${areaId}/summary`);
}

export async function getTileManifest(areaSlug: string): Promise<TileManifest> {
  const data = await fetchJson<unknown>(`${BASE}/areas/${areaSlug}/tiles`);
  return TileManifestSchema.parse(data);
}

export async function getCachedExposure(
  areaSlug: string,
  directionDeg: number,
  windSpeedMs: number,
  windGustMs?: number | null,
  bbox?: [number, number, number, number],
): Promise<FeatureResult[]> {
  const params = new URLSearchParams({
    direction_deg: String(normalizeDirectionDeg(directionDeg)),
    wind_speed_ms: String(windSpeedMs),
  });
  if (windGustMs != null && windGustMs > 0) {
    params.set("wind_gust_ms", String(windGustMs));
  }
  if (bbox) {
    params.set("bbox", bbox.join(","));
  }
  const data = await fetchJson<unknown[]>(
    `${BASE}/areas/${areaSlug}/exposure?${params}`,
  );
  return data.map((r) => FeatureResultSchema.parse(r));
}

export async function getDataQuality(areaId: number): Promise<DataQuality> {
  const data = await fetchJson<unknown>(`${BASE}/areas/${areaId}/data-quality`);
  return DataQualitySchema.parse(data);
}

export async function getAreas(): Promise<Area[]> {
  const data = await fetchJson<unknown[]>(`${BASE}/areas`);
  return data.map((a) => AreaSchema.parse(a));
}

export async function createScenario(body: {
  area_slug: string;
  wind_speed_ms: number;
  wind_direction_deg: number;
  scenario_type: "manual" | "current_weather" | "forecast";
  weather_observation_id?: number;
}): Promise<Scenario> {
  const data = await fetchJson<unknown>(`${BASE}/scenarios/scalar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return ScenarioSchema.parse(data);
}

export async function getScenarioResults(scenarioId: number): Promise<FeatureResult[]> {
  const data = await fetchJson<unknown[]>(`${BASE}/scenarios/${scenarioId}/results`);
  return data.map((r) => FeatureResultSchema.parse(r));
}

export async function getFeatureExplanation(
  featureId: number,
  scenarioId: number,
): Promise<FeatureResult> {
  const data = await fetchJson<unknown>(
    `${BASE}/features/${featureId}/explanation?scenario_id=${scenarioId}`,
  );
  return FeatureResultSchema.parse(data);
}

export async function getCurrentWeather(areaId: number): Promise<Weather> {
  const data = await fetchJson<unknown>(`${BASE}/weather/current?area_id=${areaId}`);
  return WeatherSchema.parse(data);
}

export async function getForecastWeather(areaId: number): Promise<Weather[]> {
  const data = await fetchJson<unknown[]>(`${BASE}/weather/forecast?area_id=${areaId}`);
  return data.map((row) => WeatherSchema.parse(row));
}

export async function refreshWeather(areaId: number): Promise<void> {
  await fetchJson(`${BASE}/weather/refresh?area_id=${areaId}`, { method: "POST" });
}

export async function getAreaLayers(areaId: number): Promise<{
  features: { id: number; feature_type: string; name: string | null; geom: GeoJSON.Geometry }[];
  vector_zones: { id: number; name: string; zone_type: string; status: string; boundary: GeoJSON.Geometry }[];
}> {
  return fetchJson(`${BASE}/areas/${areaId}/layers`);
}

export async function getValidationCases(areaId?: number): Promise<{
  id: number;
  name: string;
  case_type: string;
  area_id: number;
  sample_count: number;
}[]> {
  const q = areaId != null ? `?area_id=${areaId}` : "";
  return fetchJson(`${BASE}/validation/cases${q}`);
}

export async function runValidation(caseId: number): Promise<{
  validation_case_id: number;
  overall_accuracy: number;
  high_wind_recall: number | null;
  high_wind_precision: number | null;
  adjacent_class_accuracy: number;
  metrics_json: Record<string, unknown>;
}> {
  return fetchJson(`${BASE}/validation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ validation_case_id: caseId }),
  });
}

export async function seedValidation(areaSlug: string): Promise<{ validation_case_id: number }> {
  return fetchJson(`${BASE}/validation/seed?area_slug=${areaSlug}`, { method: "POST" });
}

export async function submitFeedback(body: {
  area_id: number;
  feature_id?: number;
  feedback_type: string;
  description: string;
  wind_direction_deg?: number;
}): Promise<void> {
  await fetchJson(`${BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}