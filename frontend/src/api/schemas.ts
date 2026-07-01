import { z } from "zod";

export const HealthSchema = z.object({
  status: z.string(),
  version: z.string(),
}).strict();

export const AreaSchema = z.object({
  id: z.number(),
  slug: z.string(),
  name: z.string(),
  area_type: z.string(),
  center_lat: z.number(),
  center_lon: z.number(),
  default_zoom: z.number(),
  active: z.boolean(),
}).strict();

export const ScenarioRequestSchema = z.object({
  area_slug: z.string(),
  wind_speed_ms: z.number(),
  wind_direction_deg: z.number(),
  scenario_type: z.enum(["manual", "current_weather", "forecast"]),
  weather_observation_id: z.number().optional(),
  wind_gust_ms: z.number().optional(),
}).strict();

export const ScenarioSchema = z.object({
  scenario_id: z.number(),
  area_slug: z.string(),
  wind_speed_ms: z.number(),
  wind_direction_deg: z.number(),
  scenario_type: z.string(),
  feature_count: z.number(),
  model_version: z.string(),
  data_version: z.string(),
}).strict();

export const FeatureResultSchema = z.object({
  feature_id: z.number(),
  feature_type: z.string(),
  name: z.string().nullable(),
  subtype: z.string().nullable().optional(),
  geom: z.record(z.string(), z.unknown()),
  risk_score: z.number(),
  exposure_class: z.string(),
  local_multiplier: z.number(),
  approx_local_speed_ms: z.number().nullable(),
  gust_sensitive: z.boolean(),
  confidence: z.number(),
  handling_mode: z.string(),
  subscores: z.record(z.string(), z.unknown()),
  cause_tags: z.array(z.string()),
  mitigation_tags: z.array(z.string()),
  model_note: z.string().nullable(),
  limitations: z.array(z.string()),
  cache_hit: z.boolean().nullish(),
  cache_direction_deg: z.number().nullish(),
}).strict();

export const WeatherSchema = z.object({
  area_id: z.number(),
  wind_speed_10m_ms: z.number().nullable(),
  wind_direction_10m_deg: z.number().nullable(),
  wind_gust_10m_ms: z.number().nullable(),
  timestamp: z.string(),
  source: z.string(),
  is_forecast: z.boolean().optional(),
  forecast_timestamp: z.string().nullable().optional(),
}).strict();

export const TileManifestSchema = z.object({
  area_slug: z.string(),
  ready: z.boolean(),
  base_pmtiles: z.boolean(),
  exposure_pmtiles: z.record(z.string(), z.boolean()),
  tippecanoe_available: z.boolean(),
  tiles_path: z.string(),
}).strict();

export const DataQualitySchema = z.object({
  area_id: z.number(),
  building_count: z.number(),
  official_height_coverage: z.number(),
  estimated_height_coverage: z.number(),
  fallback_height_coverage: z.number(),
  missing_height_count: z.number(),
  roads_with_inferred_width: z.number(),
  vegetation_count: z.number(),
  special_geometry_counts: z.record(z.string(), z.number()),
  low_confidence_count: z.number(),
}).strict();

export type TileManifest = z.infer<typeof TileManifestSchema>;
export type Area = z.infer<typeof AreaSchema>;
export type DataQuality = z.infer<typeof DataQualitySchema>;
export type Scenario = z.infer<typeof ScenarioSchema>;
export type FeatureResult = z.infer<typeof FeatureResultSchema>;
export type Weather = z.infer<typeof WeatherSchema>;