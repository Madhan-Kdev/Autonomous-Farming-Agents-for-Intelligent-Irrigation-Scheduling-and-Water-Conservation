/**
 * ConsolidatedScheduleCard — Task 3.2
 *
 * Multi-Zone Farm Irrigation Schedule & Hydraulic Deconfliction Timeline.
 * Shows coordinated, non-overlapping sequential irrigation windows across
 * all active zones, respecting shared pump flow limits and water budgets.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  CalendarClock,
  Clock,
  Droplets,
  Activity,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Gauge,
  Sliders,
  ShieldAlert,
  ArrowRight,
} from 'lucide-react';
import type { FarmScheduleOut, ZoneIrrigationPlan } from '../../../types';
import { fetchFarmSchedule } from '../api';

interface ConsolidatedScheduleCardProps {
  farmId: number;
  farmName?: string;
}

const PRIORITY_BADGES: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 text-red-300 border-red-500/30',
  HIGH: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  MEDIUM: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  LOW: 'bg-slate-700/50 text-slate-400 border-slate-600',
  NONE: 'bg-slate-800 text-slate-500 border-slate-700',
};

export const ConsolidatedScheduleCard: React.FC<ConsolidatedScheduleCardProps> = ({
  farmId,
  farmName = 'Demo Farm',
}) => {
  const [schedule, setSchedule] = useState<FarmScheduleOut | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [pumpCapacity, setPumpCapacity] = useState<number>(50000);
  const [waterBudget, setWaterBudget] = useState<number | undefined>(undefined);
  const [showConfig, setShowConfig] = useState<boolean>(false);

  const loadSchedule = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchFarmSchedule(farmId, waterBudget, pumpCapacity);
      setSchedule(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load consolidated farm schedule');
    } finally {
      setLoading(false);
    }
  }, [farmId, waterBudget, pumpCapacity]);

  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-xl">
            <CalendarClock className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-100">
                Consolidated Multi-Zone Farm Schedule
              </h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                Hydraulic Deconfliction
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Coordinated, conflict-free sequential irrigation windows enforcing pump capacity ({pumpCapacity.toLocaleString()} L/h)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>{showConfig ? 'Hide Config' : 'Configure Pump & Budget'}</span>
          </button>
          <button
            onClick={loadSchedule}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
            title="Refresh Schedule"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Configuration Drawer */}
      {showConfig && (
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3 text-xs animate-fadeIn">
          <span className="font-bold text-slate-200 block">Hydraulic & Budget Parameters</span>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-slate-400">Main Pump Flow Capacity (L/h)</label>
              <input
                type="number"
                min="10000"
                max="200000"
                step="5000"
                value={pumpCapacity}
                onChange={(e) => setPumpCapacity(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-400">Shared Water Budget (Liters, optional)</label>
              <input
                type="number"
                min="10000"
                max="2000000"
                step="25000"
                placeholder="Unlimited"
                value={waterBudget ?? ''}
                onChange={(e) => setWaterBudget(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200"
              />
            </div>
          </div>
          <button
            onClick={() => { setShowConfig(false); loadSchedule(); }}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold transition"
          >
            Recompute Coordinated Schedule
          </button>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="h-48 flex flex-col items-center justify-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs">Computing hydraulic deconfliction and zone time slots...</span>
        </div>
      ) : schedule ? (
        <div className="space-y-6">
          {/* Top Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Total Farm Water</span>
              <span className="text-xl font-extrabold text-blue-300 font-mono">
                {(schedule.total_farm_volume_liters / 1000).toFixed(1)}{' '}
                <span className="text-xs text-slate-400 font-normal">kL</span>
              </span>
              <span className="text-[10px] text-slate-500 block">
                Avg depth: {schedule.total_farm_volume_mm_avg.toFixed(1)} mm
              </span>
            </div>

            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Pumping Duration</span>
              <span className="text-xl font-extrabold text-slate-200 font-mono">
                {(schedule.total_pumping_duration_minutes / 60).toFixed(1)}{' '}
                <span className="text-xs text-slate-400 font-normal">hours</span>
              </span>
              <span className="text-[10px] text-slate-500 block">
                {schedule.total_pumping_duration_minutes.toFixed(0)} minutes total
              </span>
            </div>

            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Active Zones</span>
              <span className="text-xl font-extrabold text-emerald-300 font-mono">
                {schedule.zones_requiring_irrigation}{' '}
                <span className="text-xs text-slate-400 font-normal">
                  / {schedule.scheduled_zones.length}
                </span>
              </span>
              <span className="text-[10px] text-slate-500 block">Zones requiring refill</span>
            </div>

            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-1">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Deconfliction Status</span>
              <div className="flex items-center gap-1.5 pt-0.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-bold text-emerald-300">
                  {schedule.conflicts_resolved} Staggered
                </span>
              </div>
              <span className="text-[10px] text-slate-500 block">Zero hydraulic clash</span>
            </div>
          </div>

          {/* Water Rationing Alert if active */}
          {schedule.rationing_applied && (
            <div className="p-3 bg-amber-950/30 border border-amber-500/30 rounded-xl flex items-center gap-2.5 text-xs text-amber-300">
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Water Budget Rationing Active:</strong> Total farm demand exceeded available budget ({schedule.water_budget_liters?.toLocaleString()} L). Water has been prioritized for critical zones and scaled for non-critical blocks.
              </span>
            </div>
          )}

          {/* Sequential Timeline List */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-slate-300 block">
              Sequential Zone Execution Timeline
            </span>

            <div className="space-y-2">
              {schedule.scheduled_zones.map((zone: ZoneIrrigationPlan) => (
                <div
                  key={zone.zone_id}
                  className={`p-4 rounded-xl border transition flex flex-col md:flex-row md:items-center justify-between gap-3 ${
                    zone.irrigation_required
                      ? 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                      : 'bg-slate-950/40 border-slate-900 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-7 h-7 rounded-lg text-xs font-bold flex items-center justify-center font-mono ${
                        zone.irrigation_required
                          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                          : 'bg-slate-800 text-slate-500'
                      }`}
                    >
                      #{zone.sequence_order}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">{zone.zone_name}</span>
                        {zone.crop_name && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                            {zone.crop_name}
                          </span>
                        )}
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${
                            PRIORITY_BADGES[zone.priority] || 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {zone.priority}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500">
                        {zone.irrigation_method || 'drip'} &bull; Area: {zone.area_ha ?? 1.0} ha &bull; Stress: {(zone.stress_index * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  {zone.irrigation_required ? (
                    <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
                      {/* Execution Window */}
                      <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-300">
                        <Clock className="w-3.5 h-3.5 text-blue-400" />
                        <span className="font-bold">{zone.start_time} &rarr; {zone.end_time}</span>
                        <span className="text-[10px] text-blue-400/80">({zone.duration_minutes?.toFixed(0)}m)</span>
                      </div>

                      {/* Volume */}
                      <div className="text-right">
                        <span className="font-bold text-slate-200 block">
                          {zone.recommended_volume_mm.toFixed(1)} mm
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {((zone.volume_liters || 0) / 1000).toFixed(1)} kL
                        </span>
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500 font-medium">No irrigation scheduled</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
