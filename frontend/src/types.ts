export interface Farm {
  id: number;
  name: string;
  owner_name: string | null;
  latitude: number;
  longitude: number;
  altitude_m: number | null;
  total_area_ha: number | null;
  fields: Field[];
}

export interface Field {
  id: number;
  farm_id: number;
  name: string;
  area_ha: number;
  soil_type: string | null;
  zones: Zone[];
}

export interface Zone {
  id: number;
  field_id: number;
  zone_number: number;
  name: string;
  area_ha: number;
  crop_name: string | null;
  irrigation_method: string | null;
  is_active: boolean;
  min_irrigation_mm: number | null;
  max_irrigation_mm: number | null;
}

export interface WeatherContext {
  temperature_c?: number;
  humidity_pct?: number;
  wind_speed_ms?: number;
  rainfall_mm?: number;
  solar_radiation_mjm2?: number;
  forecast_rainfall_7d_mm?: number;
  irrigation_suitable?: boolean;
  weather_summary?: string;
}

export interface SoilContext {
  soil_moisture_pct?: number;
  field_capacity_pct?: number;
  wilting_point_pct?: number;
  available_water_pct?: number;
  soil_stress_index?: number;
  is_over_wet?: boolean;
  is_over_dry?: boolean;
}

export interface CropContext {
  crop_type?: string;
  growth_stage?: string;
  crop_coefficient_kc?: number;
  crop_water_requirement_mm?: number;
}

export interface ET0Context {
  et0_reference_mm?: number;
  et0_predicted_mm?: number;
  etc_mm?: number;
}

export interface IrrigationDecisionContext {
  decision: 'REQUIRED' | 'POSTPONED' | 'NOT_REQUIRED' | 'INSUFFICIENT_DATA';
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';
  recommended_time?: string;
  recommended_volume_mm?: number;
  postponement_reason?: string;
  confidence?: number;
}

export interface ZoneIrrigationPlan {
  zone_id: number;
  zone_name: string;
  irrigation_required: boolean;
  recommended_volume_mm: number;
  priority: string;
  stress_index: number;
  evidence: string[];
}

export interface OptimizationContext {
  baseline_volume_mm?: number;
  optimized_volume_mm?: number;
  water_saving_mm?: number;
  water_saving_pct?: number;
  over_irrigation_detected?: boolean;
  under_irrigation_risk?: boolean;
  evidence?: string[];
}

export interface RiskItem {
  risk_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  description: string;
  evidence: string[];
  mitigation: string;
}

export interface RiskContext {
  risks: RiskItem[];
  overall_risk_level: string;
  recommendation_safe: boolean;
  risk_summary: string;
}

export interface AdvisoryContext {
  irrigation_required: boolean;
  recommended_action: string;
  recommended_time?: string;
  recommended_volume_mm?: number;
  target_zones: number[];
  weather_influence: string;
  soil_influence: string;
  crop_influence: string;
  et0_influence: string;
  rainfall_influence: string;
  risk_summary: string;
  water_conservation_summary: string;
  full_explanation: string;
  confidence: number;
}

export interface AgentExecutionRecord {
  agent_name: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
  duration_ms?: number;
}

export interface AgentState {
  run_id: string;
  weather: WeatherContext;
  soil: SoilContext;
  crop: CropContext;
  et0: ET0Context;
  zone_plans: ZoneIrrigationPlan[];
  irrigation_decision: IrrigationDecisionContext;
  optimization: OptimizationContext;
  risk: RiskContext;
  advisory: AdvisoryContext;
  agent_executions: AgentExecutionRecord[];
  is_complete: boolean;
  workflow_step: string;
}

export interface ScenarioOverrides {
  override_temperature_c?: number;
  override_humidity_pct?: number;
  override_wind_speed_ms?: number;
  override_rainfall_mm?: number;
  override_solar_radiation_mjm2?: number;
  override_soil_moisture_pct?: number;
  crop_type?: string;
}
