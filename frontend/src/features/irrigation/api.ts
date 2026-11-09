import axios from 'axios';
import type {
  Farm,
  CropOut,
  DetailedAgentState,
  IrrigationDecisionRequest,
  IrrigationHistoryRecord,
} from './types';

export interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export const fetchFarms = async (): Promise<Farm[]> => {
  const res = await axios.get<APIResponse<Farm[]>>('/api/v1/farms');
  return res.data.success ? res.data.data : [];
};

export const fetchCrops = async (): Promise<CropOut[]> => {
  const res = await axios.get<APIResponse<CropOut[]>>('/api/v1/crops');
  return res.data.success ? res.data.data : [];
};

export const executeIrrigationDecision = async (
  req: IrrigationDecisionRequest
): Promise<DetailedAgentState> => {
  const res = await axios.post<APIResponse<DetailedAgentState>>(
    '/api/v1/irrigation/decision',
    req
  );
  if (!res.data.success) {
    throw new Error(res.data.error || res.data.message || 'Execution failed');
  }
  return res.data.data;
};

export const fetchIrrigationHistory = async (
  farmId?: number,
  zoneId?: number,
  limit = 20
): Promise<IrrigationHistoryRecord[]> => {
  const params: Record<string, any> = { limit };
  if (farmId) params.farm_id = farmId;
  if (zoneId) params.zone_id = zoneId;

  const res = await axios.get<APIResponse<IrrigationHistoryRecord[]>>(
    '/api/v1/irrigation/history',
    { params }
  );
  return res.data.success ? res.data.data : [];
};
