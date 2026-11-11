import axios from 'axios';
import type {
  Farm,
  ManualIrrigationRequest,
  ManualIrrigationOut,
  SimulationAdvanceRequest,
  SimulationStepOut,
  BatchAdvanceRequest,
  BatchAdvanceOut,
  IrrigationHistoryRecord,
  SoilTelemetryRecord,
  ET0DerivationOut,
  CalculateET0Request,
  ConservationSummary,
  RLBenchmarkRequest,
  PolicyComparisonOut,
  FarmScheduleOut,
} from '../../types';

export interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export const fetchFarmDigitalTwin = async (farmId?: number): Promise<Farm | null> => {
  const res = await axios.get<APIResponse<Farm[]>>('/api/v1/farms');
  if (res.data.success && res.data.data.length > 0) {
    if (farmId) {
      const match = res.data.data.find(f => f.id === farmId);
      return match || res.data.data[0];
    }
    return res.data.data[0];
  }
  return null;
};

export const fetchAllFarms = async (): Promise<Farm[]> => {
  const res = await axios.get<APIResponse<Farm[]>>('/api/v1/farms');
  return res.data.success ? res.data.data : [];
};

export const applyManualIrrigation = async (
  req: ManualIrrigationRequest
): Promise<ManualIrrigationOut> => {
  const res = await axios.post<APIResponse<ManualIrrigationOut>>(
    '/api/v1/simulation/irrigate-manual',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Manual irrigation failed');
  }
  return res.data.data;
};

export const advanceSimulationDay = async (
  req: SimulationAdvanceRequest
): Promise<SimulationStepOut> => {
  const res = await axios.post<APIResponse<SimulationStepOut>>(
    '/api/v1/simulation/advance',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Simulation advance failed');
  }
  return res.data.data;
};

export const batchAdvanceSimulation = async (
  req: BatchAdvanceRequest
): Promise<BatchAdvanceOut> => {
  const res = await axios.post<APIResponse<BatchAdvanceOut>>(
    '/api/v1/simulation/batch-advance',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Batch simulation failed');
  }
  return res.data.data;
};

export const fetchZoneIrrigationHistory = async (
  zoneId: number,
  limit: number = 30
): Promise<IrrigationHistoryRecord[]> => {
  const res = await axios.get<APIResponse<IrrigationHistoryRecord[]>>(
    `/api/v1/agents/zones/${zoneId}/history?limit=${limit}`
  );
  return res.data.success ? res.data.data : [];
};

export const fetchZoneSoilHistory = async (
  zoneId: number,
  limit: number = 30
): Promise<SoilTelemetryRecord[]> => {
  const res = await axios.get<APIResponse<SoilTelemetryRecord[]>>(
    `/api/v1/agents/zones/${zoneId}/soil-history?limit=${limit}`
  );
  return res.data.success ? res.data.data : [];
};

export const fetchET0Derivation = async (
  farmId: number = 1,
  cropName?: string,
  growthStage: string = 'mid',
  targetDate?: string
): Promise<ET0DerivationOut> => {
  const params = new URLSearchParams();
  params.append('farm_id', farmId.toString());
  if (cropName) params.append('crop_name', cropName);
  if (growthStage) params.append('growth_stage', growthStage);
  if (targetDate) params.append('target_date', targetDate);

  const res = await axios.get<APIResponse<ET0DerivationOut>>(
    `/api/v1/et0/derivation?${params.toString()}`
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Failed to fetch ET0 derivation');
  }
  return res.data.data;
};

export const calculateCustomET0 = async (
  req: CalculateET0Request
): Promise<ET0DerivationOut> => {
  const res = await axios.post<APIResponse<ET0DerivationOut>>(
    '/api/v1/et0/calculate',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Custom ET0 calculation failed');
  }
  return res.data.data;
};

// ─── Task 2.2: Water Conservation Summary Board ──────────────────────────────

export const fetchConservationSummary = async (
  farmId: number,
  days: number = 14,
  conventionalDailyMm: number = 6.0
): Promise<ConservationSummary> => {
  const res = await axios.get<APIResponse<ConservationSummary>>(
    '/api/v1/analytics/conservation-summary',
    { params: { farm_id: farmId, days, conventional_daily_mm: conventionalDailyMm } }
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Failed to load conservation summary');
  }
  return res.data.data;
};

// ─── Task 3.1: DRL PPO Benchmark ─────────────────────────────────────────────

export const benchmarkRLPolicy = async (
  req: RLBenchmarkRequest
): Promise<PolicyComparisonOut> => {
  const res = await axios.post<APIResponse<PolicyComparisonOut>>(
    '/api/v1/rl/benchmark',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'PPO policy benchmarking failed');
  }
  return res.data.data;
};

// ─── Task 3.2: Multi-Zone Farm Schedule & Hydraulic Deconfliction ────────────

export const fetchFarmSchedule = async (
  farmId: number,
  waterBudgetLiters?: number,
  pumpCapacityLh: number = 50000.0
): Promise<FarmScheduleOut> => {
  const params: Record<string, any> = { pump_capacity_l_h: pumpCapacityLh };
  if (waterBudgetLiters !== undefined && waterBudgetLiters !== null) {
    params.water_budget_liters = waterBudgetLiters;
  }
  const res = await axios.get<APIResponse<FarmScheduleOut>>(
    `/api/v1/farms/${farmId}/schedule`,
    { params }
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Failed to fetch farm schedule');
  }
  return res.data.data;
};
