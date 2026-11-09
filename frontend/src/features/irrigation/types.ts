import type { Farm, Field, Zone, WeatherContext, SoilContext, CropContext, ET0Context, ZoneIrrigationPlan, IrrigationDecisionContext, OptimizationContext, RiskContext, AdvisoryContext, RiskItem } from '../../types';

export type { Farm, Field, Zone, WeatherContext, SoilContext, CropContext, ET0Context, ZoneIrrigationPlan, IrrigationDecisionContext, OptimizationContext, RiskContext, AdvisoryContext, RiskItem };

export interface CropOut {
  id: number;
  name: string;
  scientific_name?: string | null;
  crop_type?: string | null;
  kc_initial: number;
  kc_mid: number;
  kc_end: number;
  root_depth_initial_m: number;
  root_depth_max_m: number;
  depletion_fraction_p: number;
  days_initial: number;
  days_development: number;
  days_mid: number;
  days_late: number;
  total_growing_days: number;
}

export interface DetailedAgentExecutionRecord {
  agent_name: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  confidence?: number | null;
}

export interface DetailedAgentState {
  run_id: string;
  created_at?: string;
  request?: {
    farm_id?: number;
    field_id?: number | null;
    zone_ids?: number[];
    crop_type?: string | null;
    override_temperature_c?: number | null;
    override_humidity_pct?: number | null;
    override_wind_speed_ms?: number | null;
    override_rainfall_mm?: number | null;
    override_soil_moisture_pct?: number | null;
    override_growth_stage?: string | null;
    override_field_capacity_pct?: number | null;
    override_wilting_point_pct?: number | null;
    override_soil_type?: string | null;
    override_water_availability_status?: string | null;
    override_available_water_liters?: number | null;
    use_historical_data?: boolean;
    use_et0_prediction?: boolean;
    run_full_workflow?: boolean;
  };
  weather: WeatherContext;
  soil: SoilContext;
  crop: CropContext;
  et0: ET0Context;
  historical?: {
    days_analyzed?: number;
    average_daily_water_applied_mm?: number;
    irrigation_efficiency_pct?: number;
    audit_findings?: string[];
  };
  zone_plans: ZoneIrrigationPlan[];
  irrigation_decision: IrrigationDecisionContext;
  optimization: OptimizationContext;
  risk: RiskContext;
  advisory: AdvisoryContext;
  agent_executions: DetailedAgentExecutionRecord[];
  errors: string[];
  warnings: string[];
  workflow_step: string;
  is_complete: boolean;
}

export interface IrrigationDecisionRequest {
  farm_id: number;
  field_id?: number | null;
  zone_id?: number | null;
  crop_type?: string | null;
  growth_stage?: 'initial' | 'development' | 'mid' | 'late' | null;

  // Soil
  soil_moisture?: number | null;
  field_capacity?: number | null;
  wilting_point?: number | null;
  soil_type?: string | null;

  // Weather
  temperature?: number | null;
  humidity?: number | null;
  wind_speed?: number | null;
  rainfall?: number | null;
  rain_probability?: number | null;
  forecast_rainfall?: number | null;

  // Water availability
  water_availability?: 'Normal' | 'Limited' | 'Low' | 'Critical' | null;
  available_water_liters?: number | null;

  // Execution toggles
  use_historical_data: boolean;
  use_et0_prediction: boolean;
  run_full_workflow: boolean;
  user_notes?: string | null;
}

export interface IrrigationHistoryRecord {
  id: number;
  farm_id: number;
  zone_id: number;
  scheduled_at: string | null;
  decision: string;
  recommended_volume_mm: number;
  recommended_duration_min: number;
  actual_volume_mm?: number | null;
  was_applied?: boolean;
  soil_moisture_before_pct?: number | null;
  et0_on_day_mm?: number | null;
  etc_on_day_mm?: number | null;
  precipitation_on_day_mm?: number | null;
  decision_confidence?: number | null;
  reasoning_summary?: string | null;
}

export type PresetKey =
  | 'normal'
  | 'dry'
  | 'rainy'
  | 'drought'
  | 'saturated'
  | 'high_wind'
  | 'frost'
  | 'low_water';

export interface PresetScenario {
  id: PresetKey;
  label: string;
  badge: string;
  description: string;
  values: Partial<IrrigationDecisionRequest>;
}
