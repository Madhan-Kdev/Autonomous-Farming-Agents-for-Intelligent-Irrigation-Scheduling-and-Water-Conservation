import axios from 'axios';
import type {
  Farm,
  ManualIrrigationRequest,
  ManualIrrigationOut,
  SimulationAdvanceRequest,
  SimulationStepOut,
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

