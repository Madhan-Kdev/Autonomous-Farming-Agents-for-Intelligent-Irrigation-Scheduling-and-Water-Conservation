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
  latest_soil_moisture_pct?: number | null;
  field_capacity_pct?: number | null;
  wilting_point_pct?: number | null;
  stress_index?: number | null;
}

export interface ManualIrrigationRequest {
  zone_id: number;
  volume_mm?: number | null;
  volume_liters?: number | null;
  irrigation_method?: string | null;
  flow_rate_l_h?: number | null;
}

export interface ManualIrrigationOut {
  zone_id: number;
  zone_name: string;
  farm_id: number;
  volume_applied_mm: number;
  volume_applied_liters: number;
  duration_minutes: number;
  flow_rate_l_h: number;
  irrigation_method: string;
  soil_moisture_before_pct: number;
  soil_moisture_after_pct: number;
  field_capacity_pct: number;
  wilting_point_pct: number;
  deep_percolation_mm: number;
  stress_index_before: number;
  stress_index_after: number;
  irrigation_record_id: number;
  soil_profile_id: number;
}

export interface SimulationAdvanceRequest {
  farm_id: number;
  target_date?: string | null;
  irrigation_events?: Record<number, number>;
  force_rain_mm?: number | null;
}

export interface SimulationStepOut {
  target_date: string;
  weather_record_id: number;
  soil_profiles_updated: number[];
  simulated_et0_mm: number;
  simulated_rain_mm: number;
  zone_moisture_levels: Record<number, number>;
}

export interface BatchAdvanceRequest {
  farm_id: number;
  days?: number;
  force_rain_daily_mm?: number | null;
  zone_irrigation_daily_mm?: Record<number, number>;
  auto_irrigate_threshold_pct?: number | null;
}

export interface BatchAdvanceSummary {
  total_rain_mm: number;
  total_et0_mm: number;
  zone_final_moistures: Record<number, number>;
  zone_stress_days: Record<number, number>;
}

export interface BatchAdvanceOut {
  farm_id: number;
  days_simulated: number;
  start_date: string;
  end_date: string;
  daily_results: SimulationStepOut[];
  summary: BatchAdvanceSummary;
}

export interface IrrigationHistoryRecord {
  id: number;
  scheduled_at: string | null;
  decision: string;
  recommended_volume_mm?: number | null;
  recommended_duration_min?: number | null;
  actual_volume_mm?: number | null;
  actual_duration_min?: number | null;
  was_applied: boolean;
  soil_moisture_before_pct?: number | null;
  soil_moisture_after_pct?: number | null;
  et0_on_day_mm?: number | null;
  etc_on_day_mm?: number | null;
  precipitation_on_day_mm?: number | null;
  irrigation_method?: string | null;
  reasoning_summary?: string | null;
}

export interface SoilTelemetryRecord {
  id: number;
  created_at: string | null;
  volumetric_moisture_pct: number;
  field_capacity_pct?: number | null;
  wilting_point_pct?: number | null;
  temperature_c?: number | null;
  data_source?: string | null;
  notes?: string | null;
}

export interface ET0Step {
  step_number: number;
  title: string;
  fao_equation: string;
  formula_latex: string;
  result_value: number;
  result_unit: string;
  scientific_note: string;
}

export interface CropETcOut {
  crop_name: string;
  growth_stage: string;
  kc: number;
  etc_mm: number;
  daily_water_liters_per_ha: number;
}

export interface ET0DerivationOut {
  et0_mm: number;
  radiation_term_mm: number;
  aerodynamic_term_mm: number;
  radiation_share_pct: number;
  aerodynamic_share_pct: number;
  t_mean_c: number;
  pressure_kpa: number;
  gamma_kpa_c: number;
  es_kpa: number;
  ea_kpa: number;
  vpd_kpa: number;
  delta_kpa_c: number;
  ra_mj_m2: number;
  rso_mj_m2: number;
  rns_mj_m2: number;
  rnl_mj_m2: number;
  rn_mj_m2: number;
  wind_speed_m_s: number;
  solar_radiation_mj_m2: number;
  crop_etc?: CropETcOut | null;
  steps: ET0Step[];
}

export interface CalculateET0Request {
  temp_max_c: number;
  temp_min_c: number;
  humidity_max_pct?: number;
  humidity_min_pct?: number;
  wind_speed_m_s?: number;
  solar_radiation_mj_m2?: number;
  altitude_m?: number;
  latitude_deg?: number;
  day_of_year?: number | null;
  crop_name?: string | null;
  growth_stage?: string | null;
  custom_kc?: number | null;
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

// ─── Task 2.2: Water Conservation Summary Board ──────────────────────────────

export interface DailyConservationPoint {
  date: string;
  water_applied_mm: number;
  etc_demand_mm: number;
  precipitation_mm: number;
  conventional_mm: number;
  saved_mm: number;
  decisions: string[];
}

export interface ConservationSummary {
  farm_id: number;
  farm_name: string;
  window_days: number;
  window_start: string;
  window_end: string;
  // Actual intelligent-system metrics
  total_water_applied_mm: number;
  total_water_applied_liters: number;
  total_etc_demand_mm: number;
  total_precipitation_mm: number;
  // Decision breakdown
  total_decisions: number;
  decisions_required: number;
  decisions_postponed: number;
  decisions_not_required: number;
  decisions_manual: number;
  // Efficiency
  iwue: number;
  average_confidence: number;
  // Conservation estimate (model-based)
  conventional_daily_mm: number;
  conventional_total_mm: number;
  water_saved_mm: number;
  water_saved_pct: number;
  water_saved_liters: number;
  // Trend
  daily_trend: DailyConservationPoint[];
  disclaimer: string;
}
