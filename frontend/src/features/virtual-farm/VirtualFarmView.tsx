import React, { useState, useEffect, useMemo } from 'react';
import {
  Droplets,
  Calendar,
  CloudSun,
  AlertTriangle,
  Play,
  RotateCcw,
  Sparkles,
  Info,
  CheckCircle2,
  Gauge,
  Sliders,
  ChevronRight,
  TrendingDown,
  Waves,
  History,
  BarChart2,
  Activity,
  Clock,
  Sun,
  CloudRain,
  Zap,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import type {
  Farm,
  Zone,
  ManualIrrigationOut,
  SimulationStepOut,
  BatchAdvanceOut,
  IrrigationHistoryRecord,
  SoilTelemetryRecord,
} from '../../types';
import {
  fetchFarmDigitalTwin,
  fetchAllFarms,
  applyManualIrrigation,
  advanceSimulationDay,
  batchAdvanceSimulation,
  fetchZoneIrrigationHistory,
  fetchZoneSoilHistory,
} from './api';
import { FAO56BreakdownModal } from './components/FAO56BreakdownModal';
import { WaterConservationBoard } from './components/WaterConservationBoard';
import { PPOBenchmarkCard } from './components/PPOBenchmarkCard';

interface VirtualFarmViewProps {
  onNavigateToDecision?: (farmId: number, zoneId?: number) => void;
}

export const VirtualFarmView: React.FC<VirtualFarmViewProps> = ({
  onNavigateToDecision,
}) => {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarm, setSelectedFarm] = useState<Farm | null>(null);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');

  // Manual Irrigation Modal State
  const [manualModalOpen, setManualModalOpen] = useState<boolean>(false);
  const [volumeMode, setVolumeMode] = useState<'mm' | 'liters'>('mm');
  const [irrigationDepthMm, setIrrigationDepthMm] = useState<number>(20.0);
  const [irrigationVolumeLiters, setIrrigationVolumeLiters] = useState<number>(200000);
  const [selectedMethod, setSelectedMethod] = useState<string>('drip');
  const [flowRateLh, setFlowRateLh] = useState<number>(25000);
  const [lastManualResult, setLastManualResult] = useState<ManualIrrigationOut | null>(null);

  // Simulation Stepper State
  const [forcedRainMm, setForcedRainMm] = useState<number>(0);
  const [lastSimulationStep, setLastSimulationStep] = useState<SimulationStepOut | null>(null);

  // Batch Scenario Simulation State
  const [batchModalOpen, setBatchModalOpen] = useState<boolean>(false);
  const [batchDays, setBatchDays] = useState<number>(7);
  const [batchScenario, setBatchScenario] = useState<'drydown' | 'monsoon' | 'auto-refill' | 'custom'>('drydown');
  const [batchRainMm, setBatchRainMm] = useState<number>(0);
  const [batchAutoRefillPct, setBatchAutoRefillPct] = useState<number>(18.0);
  const [lastBatchResult, setLastBatchResult] = useState<BatchAdvanceOut | null>(null);

  // FAO-56 Modal State
  const [et0ModalOpen, setEt0ModalOpen] = useState<boolean>(false);

  // History & Telemetry State
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [irrigationHistory, setIrrigationHistory] = useState<IrrigationHistoryRecord[]>([]);
  const [soilHistory, setSoilHistory] = useState<SoilTelemetryRecord[]>([]);
  const [historyTab, setHistoryTab] = useState<'chart' | 'table'>('chart');

  useEffect(() => {
    loadFarms();
  }, []);

  useEffect(() => {
    if (selectedZone) {
      loadZoneHistory(selectedZone.id);
    } else {
      setIrrigationHistory([]);
      setSoilHistory([]);
    }
  }, [selectedZone?.id, lastManualResult, lastSimulationStep]);

  const loadZoneHistory = async (zoneId: number) => {
    setHistoryLoading(true);
    try {
      const [irrigRecs, soilRecs] = await Promise.all([
        fetchZoneIrrigationHistory(zoneId, 30),
        fetchZoneSoilHistory(zoneId, 30),
      ]);
      setIrrigationHistory(irrigRecs);
      setSoilHistory(soilRecs);
    } catch (err: any) {
      console.error('Failed to load zone history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const chartData = useMemo(() => {
    const points: Array<{
      rawTime: number;
      timeLabel: string;
      moisture: number | null;
      irrigationMm: number | null;
      decision: string | null;
      wasApplied: boolean;
    }> = [];

    // Add soil profile points
    soilHistory.forEach((s) => {
      const t = s.created_at ? new Date(s.created_at).getTime() : 0;
      const d = s.created_at ? new Date(s.created_at) : new Date();
      points.push({
        rawTime: t,
        timeLabel: `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`,
        moisture: s.volumetric_moisture_pct,
        irrigationMm: null,
        decision: null,
        wasApplied: false,
      });
    });

    // Add irrigation record points
    irrigationHistory.forEach((r) => {
      const t = r.scheduled_at ? new Date(r.scheduled_at).getTime() : 0;
      const d = r.scheduled_at ? new Date(r.scheduled_at) : new Date();
      points.push({
        rawTime: t,
        timeLabel: `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`,
        moisture: r.soil_moisture_after_pct ?? r.soil_moisture_before_pct ?? null,
        irrigationMm: r.was_applied ? (r.actual_volume_mm ?? r.recommended_volume_mm ?? 0) : 0,
        decision: r.decision,
        wasApplied: r.was_applied,
      });
    });

    // Sort chronologically ascending
    points.sort((a, b) => a.rawTime - b.rawTime);
    return points.slice(-30);
  }, [soilHistory, irrigationHistory]);

  const loadFarms = async () => {
    setLoading(true);
    try {
      const allFarms = await fetchAllFarms();
      setFarms(allFarms);
      if (allFarms.length > 0) {
        setSelectedFarm(allFarms[0]);
        // Auto-select first zone if available
        if (allFarms[0].fields?.[0]?.zones?.[0]) {
          setSelectedZone(allFarms[0].fields[0].zones[0]);
        }
      }
    } catch (err: any) {
      setStatusMessage(`Failed to load farm data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFarm = (farmId: number) => {
    const f = farms.find((farm) => farm.id === farmId);
    if (f) {
      setSelectedFarm(f);
      if (f.fields?.[0]?.zones?.[0]) {
        setSelectedZone(f.fields[0].zones[0]);
      } else {
        setSelectedZone(null);
      }
      setLastManualResult(null);
    }
  };

  // Sync depth and volume conversions based on active zone area
  const activeZoneAreaHa = selectedZone?.area_ha || 1.0;

  const handleDepthChange = (depth: number) => {
    setIrrigationDepthMm(depth);
    setIrrigationVolumeLiters(Math.round(depth * activeZoneAreaHa * 10000));
  };

  const handleVolumeChange = (liters: number) => {
    setIrrigationVolumeLiters(liters);
    setIrrigationDepthMm(Number((liters / (activeZoneAreaHa * 10000)).toFixed(1)));
  };

  // Calculate pumping duration
  const activeFlowRate = flowRateLh > 0 ? flowRateLh : 25000 * activeZoneAreaHa;
  const calculatedDurationMinutes =
    activeFlowRate > 0
      ? Number(((irrigationVolumeLiters / activeFlowRate) * 60).toFixed(1))
      : 0;

  const handleApplyManualIrrigation = async () => {
    if (!selectedZone) return;
    setActionLoading(true);
    setStatusMessage(`Applying manual irrigation to ${selectedZone.name}...`);
    try {
      const result = await applyManualIrrigation({
        zone_id: selectedZone.id,
        volume_mm: volumeMode === 'mm' ? irrigationDepthMm : undefined,
        volume_liters: volumeMode === 'liters' ? irrigationVolumeLiters : undefined,
        irrigation_method: selectedMethod,
        flow_rate_l_h: flowRateLh,
      });

      setLastManualResult(result);
      setStatusMessage(
        `Applied ${result.volume_applied_mm} mm to ${result.zone_name}. Soil moisture replenished to ${result.soil_moisture_after_pct}%.`
      );

      // Refresh farm telemetry
      const updatedFarm = await fetchFarmDigitalTwin(selectedFarm?.id);
      if (updatedFarm) {
        setSelectedFarm(updatedFarm);
        const updatedZone = updatedFarm.fields
          .flatMap((f) => f.zones)
          .find((z) => z.id === selectedZone.id);
        if (updatedZone) setSelectedZone(updatedZone);
      }
    } catch (err: any) {
      setStatusMessage(`Manual irrigation failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAdvanceDay = async (days = 1, rainOverride?: number) => {
    if (!selectedFarm) return;
    setActionLoading(true);
    setStatusMessage(`Advancing simulation ${days} day(s) forward...`);
    try {
      let latestStep: SimulationStepOut | null = null;
      for (let i = 0; i < days; i++) {
        latestStep = await advanceSimulationDay({
          farm_id: selectedFarm.id,
          force_rain_mm: rainOverride !== undefined ? rainOverride : (forcedRainMm > 0 ? forcedRainMm : undefined),
        });
      }
      setLastSimulationStep(latestStep);
      setStatusMessage(
        `Virtual day advanced to ${latestStep?.target_date}. ET0: ${latestStep?.simulated_et0_mm} mm, Rain: ${latestStep?.simulated_rain_mm} mm.`
      );

      // Refresh farm state
      const updatedFarm = await fetchFarmDigitalTwin(selectedFarm.id);
      if (updatedFarm) {
        setSelectedFarm(updatedFarm);
        if (selectedZone) {
          const updatedZone = updatedFarm.fields
            .flatMap((f) => f.zones)
            .find((z) => z.id === selectedZone.id);
          if (updatedZone) setSelectedZone(updatedZone);
        }
      }
    } catch (err: any) {
      setStatusMessage(`Simulation advance failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleBatchSimulation = async (
    days: number,
    scenario: 'drydown' | 'monsoon' | 'auto-refill' | 'custom',
    rainOverride?: number,
    autoRefillThreshold?: number
  ) => {
    if (!selectedFarm) return;
    setActionLoading(true);
    setStatusMessage(`Running ${days}-day batch simulation [${scenario}]...`);
    try {
      let rainMm: number | null = null;
      let threshold: number | null = null;

      if (scenario === 'drydown') {
        rainMm = 0.0;
      } else if (scenario === 'monsoon') {
        rainMm = rainOverride !== undefined ? rainOverride : 15.0;
      } else if (scenario === 'auto-refill') {
        threshold = autoRefillThreshold !== undefined ? autoRefillThreshold : 18.0;
      } else if (scenario === 'custom') {
        rainMm = rainOverride !== undefined ? rainOverride : (batchRainMm > 0 ? batchRainMm : null);
        threshold =
          autoRefillThreshold !== undefined
            ? autoRefillThreshold
            : batchAutoRefillPct > 0
            ? batchAutoRefillPct
            : null;
      }

      const res = await batchAdvanceSimulation({
        farm_id: selectedFarm.id,
        days: days,
        force_rain_daily_mm: rainMm,
        auto_irrigate_threshold_pct: threshold,
      });

      setLastBatchResult(res);
      const latestDaily = res.daily_results[res.daily_results.length - 1];
      setLastSimulationStep(latestDaily);
      setStatusMessage(
        `Batch simulation of ${res.days_simulated} days completed (${res.start_date} to ${res.end_date}). Total Rain: ${res.summary.total_rain_mm} mm, Total ET0: ${res.summary.total_et0_mm} mm.`
      );

      // Refresh farm digital twin state
      const updatedFarm = await fetchFarmDigitalTwin(selectedFarm.id);
      if (updatedFarm) {
        setSelectedFarm(updatedFarm);
        if (selectedZone) {
          const updatedZone = updatedFarm.fields
            .flatMap((f) => f.zones)
            .find((z) => z.id === selectedZone.id);
          if (updatedZone) setSelectedZone(updatedZone);
        }
      }
    } catch (err: any) {
      setStatusMessage(`Batch simulation failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  // Helper to determine zone color by moisture
  const getZoneStatus = (zone: Zone) => {
    const moisture = zone.latest_soil_moisture_pct ?? 22.0;
    const fc = zone.field_capacity_pct ?? 30.0;
    const wp = zone.wilting_point_pct ?? 12.0;
    const stress = zone.stress_index ?? 0.0;

    if (moisture <= wp || stress > 0.6) {
      return {
        label: 'Severe Stress',
        colorClass: 'fill-red-500/20 stroke-red-500 text-red-400',
        badgeBg: 'bg-red-950/80 text-red-300 border-red-500/40',
        barColor: 'bg-red-500',
      };
    }
    if (moisture < wp + (fc - wp) * 0.45 || stress > 0.1) {
      return {
        label: 'Mild Stress',
        colorClass: 'fill-amber-500/20 stroke-amber-500 text-amber-400',
        badgeBg: 'bg-amber-950/80 text-amber-300 border-amber-500/40',
        barColor: 'bg-amber-500',
      };
    }
    if (moisture > fc * 0.98) {
      return {
        label: 'Saturated',
        colorClass: 'fill-sky-500/20 stroke-sky-500 text-sky-400',
        badgeBg: 'bg-sky-950/80 text-sky-300 border-sky-500/40',
        barColor: 'bg-sky-500',
      };
    }
    return {
      label: 'Optimal',
      colorClass: 'fill-emerald-500/20 stroke-emerald-500 text-emerald-400',
      badgeBg: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40',
      barColor: 'bg-emerald-500',
    };
  };

  const allZones = selectedFarm?.fields?.flatMap((f) => f.zones) || [];

  return (
    <div className="space-y-6">
      {/* Top Banner & Farm Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Agricultural Digital Twin Workspace
          </div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            Virtual Farm Topology & Live Zone Telemetry
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            100% simulated soil physics, root-zone moisture refill, percolation losses, and direct digital twin controls.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedFarm?.id || ''}
            onChange={(e) => handleSelectFarm(Number(e.target.value))}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            {farms.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.total_area_ha} ha)
              </option>
            ))}
          </select>

          <button
            onClick={() => handleAdvanceDay(1)}
            disabled={actionLoading}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-3.5 py-2 rounded-xl text-xs font-semibold transition disabled:opacity-50"
            title="Step simulation forward by 1 day"
          >
            <Calendar className="w-3.5 h-3.5 text-sky-400" />
            <span>Step 1 Day</span>
          </button>

          <button
            onClick={() => handleBatchSimulation(7, 'drydown')}
            disabled={actionLoading}
            className="flex items-center gap-2 bg-amber-950/60 hover:bg-amber-900/60 border border-amber-600/40 text-amber-300 px-3.5 py-2 rounded-xl text-xs font-semibold transition disabled:opacity-50"
            title="Advance 7 consecutive days with zero rainfall to simulate drought drydown"
          >
            <Sun className="w-3.5 h-3.5 text-amber-400" />
            <span>7-Day Drydown</span>
          </button>

          <button
            onClick={() => setBatchModalOpen(true)}
            disabled={actionLoading}
            className="flex items-center gap-2 bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-600/40 text-emerald-300 px-4 py-2 rounded-xl text-xs font-bold transition disabled:opacity-50"
            title="Configure and run multi-day agricultural scenarios"
          >
            <Sliders className="w-3.5 h-3.5 text-emerald-400" />
            <span>Multi-Day Scenarios...</span>
          </button>
        </div>
      </div>

      {/* Batch Simulation Summary Banner */}
      {lastBatchResult && (
        <div className="p-4 bg-sky-950/40 border border-sky-500/40 rounded-2xl text-xs space-y-3 animate-fadeIn">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sky-500/20 pb-2">
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-sky-500/20 rounded-lg text-sky-400">
                <Play className="w-4 h-4 fill-sky-400" />
              </span>
              <div>
                <span className="font-bold text-slate-100 text-sm">
                  Batch Simulation Results ({lastBatchResult.days_simulated} Days)
                </span>
                <span className="text-slate-400 text-xs ml-2">
                  {lastBatchResult.start_date} &rarr; {lastBatchResult.end_date}
                </span>
              </div>
            </div>
            <button
              onClick={() => setLastBatchResult(null)}
              className="text-slate-400 hover:text-slate-200 text-xs px-2 py-1 rounded bg-slate-800/60"
            >
              Dismiss
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-slate-300">
            <div className="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Cumulative Rain</span>
              <span className="text-sm font-bold text-sky-300">{lastBatchResult.summary.total_rain_mm} mm</span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Cumulative ET₀</span>
              <span className="text-sm font-bold text-amber-300">{lastBatchResult.summary.total_et0_mm} mm</span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Simulated Steps</span>
              <span className="text-sm font-bold text-emerald-300">{lastBatchResult.daily_results.length} Days</span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
              <span className="text-[10px] text-slate-400 block uppercase">Water Stress Days</span>
              <span className="text-sm font-bold text-red-300">
                {Object.values(lastBatchResult.summary.zone_stress_days).reduce((a, b) => a + b, 0)} Zone-Days
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-400">
            <span className="font-semibold text-slate-300">Zone Final Moisture:</span>
            {Object.entries(lastBatchResult.summary.zone_final_moistures).map(([zid, m]) => (
              <span key={zid} className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-200">
                Zone #{zid}: <strong className="text-sky-300">{m}%</strong> (Stress: {lastBatchResult.summary.zone_stress_days[Number(zid)] || 0}d)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Status banner */}
      {statusMessage && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button
            onClick={() => setStatusMessage('')}
            className="text-slate-400 hover:text-slate-200 text-xs ml-4"
          >
            ×
          </button>
        </div>
      )}

      {/* Main Grid: 2D Canvas on Left, Zone Inspection & Control on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 Columns: 2D Farm Layout Canvas */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">2D Farm Zone Layout</h3>
              <p className="text-xs text-slate-400">
                Click any zone to inspect root-zone soil balance or trigger manual irrigation.
              </p>
            </div>
            {/* Color Legend */}
            <div className="flex items-center gap-3 text-[11px]">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-slate-300">Optimal</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="text-slate-300">Mild Stress</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span className="text-slate-300">Drought</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                <span className="text-slate-300">Saturated</span>
              </span>
            </div>
          </div>

          {/* SVG 2D Interactive Map */}
          <div className="relative w-full aspect-[16/10] bg-slate-950/80 rounded-xl border border-slate-800/80 p-4 flex items-center justify-center overflow-hidden">
            <svg
              viewBox="0 0 600 380"
              className="w-full h-full select-none"
              style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }}
            >
              {/* Field Perimeter */}
              <rect
                x="20"
                y="20"
                width="560"
                height="340"
                rx="16"
                fill="#0f172a"
                stroke="#1e293b"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <text x="35" y="45" fill="#64748b" fontSize="12" fontWeight="600">
                {selectedFarm?.name || 'Farm Boundary'} • {selectedFarm?.fields?.[0]?.name || 'Field 1'} (
                {selectedFarm?.total_area_ha || 5.0} ha)
              </text>

              {/* Zones mapped side-by-side or in grid */}
              {allZones.map((zone, idx) => {
                const status = getZoneStatus(zone);
                const isSelected = selectedZone?.id === zone.id;
                // Calculate position based on 3 zones
                const total = allZones.length || 3;
                const width = (560 - 30 * (total + 1)) / total;
                const x = 30 + idx * (width + 30);
                const y = 60;
                const height = 280;

                return (
                  <g
                    key={zone.id}
                    onClick={() => {
                      setSelectedZone(zone);
                      setLastManualResult(null);
                    }}
                    className="cursor-pointer transition-transform duration-200"
                  >
                    {/* Zone background rect */}
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      rx="12"
                      className={`transition-all duration-300 ${
                        isSelected
                          ? `${status.colorClass} stroke-[3] filter drop-shadow(0 0 8px rgba(16,185,129,0.3))`
                          : `${status.colorClass} stroke-[1.5] hover:stroke-[2.5] opacity-85 hover:opacity-100`
                      }`}
                    />

                    {/* Zone Badge / Header */}
                    <rect
                      x={x + 10}
                      y={y + 12}
                      width={width - 20}
                      height="26"
                      rx="6"
                      fill="#020617"
                      fillOpacity="0.85"
                    />
                    <text
                      x={x + width / 2}
                      y={y + 29}
                      textAnchor="middle"
                      fill="#f8fafc"
                      fontSize="11"
                      fontWeight="700"
                    >
                      {zone.name}
                    </text>

                    {/* Crop Icon & Info */}
                    <text
                      x={x + width / 2}
                      y={y + 65}
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize="11"
                    >
                      Crop: <tspan fill="#f1f5f9" fontWeight="600">{zone.crop_name || 'Mixed'}</tspan>
                    </text>
                    <text
                      x={x + width / 2}
                      y={y + 85}
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize="10"
                    >
                      Area: <tspan fill="#f1f5f9">{zone.area_ha} ha</tspan> • {zone.irrigation_method || 'drip'}
                    </text>

                    {/* Moisture Display Circular / Gauge Representation */}
                    <circle
                      cx={x + width / 2}
                      cy={y + 145}
                      r="40"
                      fill="#020617"
                      stroke="#334155"
                      strokeWidth="2"
                    />
                    <text
                      x={x + width / 2}
                      y={y + 143}
                      textAnchor="middle"
                      fill="#38bdf8"
                      fontSize="16"
                      fontWeight="800"
                    >
                      {zone.latest_soil_moisture_pct?.toFixed(1) ?? '22.0'}%
                    </text>
                    <text
                      x={x + width / 2}
                      y={y + 160}
                      textAnchor="middle"
                      fill="#64748b"
                      fontSize="9"
                      fontWeight="600"
                    >
                      MOISTURE
                    </text>

                    {/* Status Pill in SVG */}
                    <rect
                      x={x + width / 2 - 45}
                      y={y + 205}
                      width="90"
                      height="22"
                      rx="11"
                      fill="#020617"
                      fillOpacity="0.9"
                      stroke="currentColor"
                      className={status.colorClass}
                      strokeWidth="1"
                    />
                    <text
                      x={x + width / 2}
                      y={y + 220}
                      textAnchor="middle"
                      className={status.colorClass}
                      fontSize="10"
                      fontWeight="700"
                    >
                      {status.label}
                    </text>

                    {/* Selection Indicator Ring */}
                    {isSelected && (
                      <circle
                        cx={x + width / 2}
                        cy={y + 250}
                        r="5"
                        fill="#10b981"
                        className="animate-ping"
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Environmental Telemetry Bar */}
          <div className="mt-4 pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => setEt0ModalOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-300 font-medium transition cursor-pointer"
                title="Inspect full 13-step thermodynamic FAO-56 derivation and crop ETc"
              >
                <CloudSun className="w-4 h-4 text-amber-400" />
                <span>Simulated ET₀: {lastSimulationStep?.simulated_et0_mm?.toFixed(1) || '4.2'} mm/day</span>
                <span className="text-[10px] text-amber-400 font-bold ml-1 bg-amber-500/20 px-1.5 py-0.5 rounded">
                  FAO-56 Breakdown &rarr;
                </span>
              </button>
              <span className="flex items-center gap-1.5">
                <Droplets className="w-4 h-4 text-sky-400" />
                <span>Rainfall: {lastSimulationStep?.simulated_rain_mm?.toFixed(1) || '0.0'} mm</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span>Rain Scenario Override:</span>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={forcedRainMm}
                onChange={(e) => setForcedRainMm(Number(e.target.value))}
                className="w-16 bg-slate-950 border border-slate-800 rounded px-2 py-0.5 text-xs text-slate-200"
              />
              <span>mm</span>
            </div>
          </div>
        </div>

        {/* Right 5 Columns: Zone Inspection & Manual Water Control */}
        <div className="lg:col-span-5 space-y-6">
          {selectedZone ? (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-slate-100">{selectedZone.name}</h3>
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-md border ${
                        getZoneStatus(selectedZone).badgeBg
                      }`}
                    >
                      {getZoneStatus(selectedZone).label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Crop: <span className="text-slate-200 font-semibold">{selectedZone.crop_name}</span> •{' '}
                    {selectedZone.area_ha} Hectares{' '}
                    <button
                      type="button"
                      onClick={() => setEt0ModalOpen(true)}
                      className="text-amber-400 hover:text-amber-300 text-[10px] underline ml-1 font-medium cursor-pointer"
                    >
                      (View ETc Breakdown)
                    </button>
                  </p>
                </div>

                <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                  <Gauge className="w-5 h-5 text-emerald-400" />
                </div>
              </div>

              {/* Moisture & Soil Physics Balance */}
              <div className="space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-400">Volumetric Moisture ($\theta$):</span>
                  <span className="text-base font-bold text-sky-300">
                    {selectedZone.latest_soil_moisture_pct?.toFixed(1) ?? '22.0'}%
                  </span>
                </div>

                {/* Progress bar showing WP, Current, FC */}
                <div className="space-y-1">
                  <div className="w-full bg-slate-950 rounded-full h-3.5 border border-slate-800 overflow-hidden relative">
                    {/* WP marker */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-red-400 z-10"
                      style={{ left: `${selectedZone.wilting_point_pct ?? 12}%` }}
                      title="Permanent Wilting Point (WP)"
                    />
                    {/* FC marker */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 z-10"
                      style={{ left: `${selectedZone.field_capacity_pct ?? 30}%` }}
                      title="Field Capacity (FC)"
                    />
                    {/* Moisture level fill */}
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        getZoneStatus(selectedZone).barColor
                      }`}
                      style={{
                        width: `${Math.min(100, (selectedZone.latest_soil_moisture_pct ?? 22) * 2)}%`,
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>WP: {selectedZone.wilting_point_pct ?? 12}%</span>
                    <span>Current: {selectedZone.latest_soil_moisture_pct?.toFixed(1) ?? 22}%</span>
                    <span>FC: {selectedZone.field_capacity_pct ?? 30}%</span>
                  </div>
                </div>

                {/* Metric Grid */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 block uppercase font-medium">
                      Soil Stress Index (Ks)
                    </span>
                    <span className="text-sm font-bold text-amber-300">
                      {selectedZone.stress_index !== undefined && selectedZone.stress_index !== null
                        ? selectedZone.stress_index.toFixed(3)
                        : '0.000'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">0.0 = No stress, 1.0 = Max</span>
                  </div>

                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 block uppercase font-medium">
                      Irrigation Method
                    </span>
                    <span className="text-sm font-bold text-slate-200 capitalize">
                      {selectedZone.irrigation_method || 'drip'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      {selectedZone.irrigation_method === 'sprinkler'
                        ? '80% efficiency'
                        : selectedZone.irrigation_method === 'flood'
                        ? '65% efficiency'
                        : '90% application efficiency'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 border-t border-slate-800 space-y-2">
                <button
                  onClick={() => setManualModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-sky-600 to-cyan-600 hover:from-sky-500 hover:to-cyan-500 text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg shadow-sky-950/50 transition"
                >
                  <Droplets className="w-4 h-4 fill-white" />
                  <span>Manual Water Application</span>
                </button>

                {onNavigateToDecision && (
                  <button
                    onClick={() => onNavigateToDecision(selectedZone.field_id, selectedZone.id)}
                    className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-emerald-300 font-medium py-2 px-4 rounded-xl text-xs border border-emerald-500/30 transition"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Run AI Agent Decision for this Zone</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Last Manual Irrigation Feedback Card */}
              {lastManualResult && (
                <div className="p-4 bg-sky-950/40 border border-sky-500/40 rounded-xl space-y-2 animate-fadeIn">
                  <div className="flex items-center gap-2 text-xs font-bold text-sky-300">
                    <CheckCircle2 className="w-4 h-4 text-sky-400" />
                    <span>Irrigation Event Applied & Logged</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300">
                    <div>
                      <span className="text-slate-500">Volume:</span>{' '}
                      <span className="font-semibold text-slate-200">
                        {lastManualResult.volume_applied_mm} mm ({lastManualResult.volume_applied_liters.toLocaleString()} L)
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Duration:</span>{' '}
                      <span className="font-semibold text-slate-200">{lastManualResult.duration_minutes} min</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Moisture:</span>{' '}
                      <span className="text-slate-400">{lastManualResult.soil_moisture_before_pct}%</span> →{' '}
                      <span className="font-bold text-emerald-400">{lastManualResult.soil_moisture_after_pct}%</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Deep Percolation:</span>{' '}
                      <span className="font-semibold text-amber-300">
                        {lastManualResult.deep_percolation_mm} mm
                      </span>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    Recorded in Database: Record #{lastManualResult.irrigation_record_id} • Soil #{lastManualResult.soil_profile_id}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center text-slate-500">
              Select a zone from the 2D layout to inspect details.
            </div>
          )}
        </div>
      </div>

      {/* Zone Irrigation & Moisture History Section */}
      {selectedZone && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-sky-500/10 border border-sky-500/20 rounded-xl">
                <Activity className="w-5 h-5 text-sky-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-100">
                    Zone Telemetry & Irrigation History
                  </h3>
                  <span className="text-xs px-2 py-0.5 rounded-md bg-slate-800 text-sky-300 font-semibold border border-slate-700">
                    {selectedZone.name}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Time-series volumetric soil moisture dynamics (&theta;) and applied irrigation events with Field Capacity & Wilting Point thresholds
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setHistoryTab('chart')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                    historyTab === 'chart'
                      ? 'bg-sky-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  <span>Telemetry Chart</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryTab('table')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
                    historyTab === 'table'
                      ? 'bg-sky-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <History className="w-3.5 h-3.5" />
                  <span>Event Log ({irrigationHistory.length})</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => loadZoneHistory(selectedZone.id)}
                disabled={historyLoading}
                className="p-2 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700 text-slate-300 transition disabled:opacity-50"
                title="Refresh history"
              >
                <RotateCcw className={`w-4 h-4 ${historyLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {historyLoading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-2 text-slate-400">
              <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs">Loading telemetry records...</span>
            </div>
          ) : historyTab === 'chart' ? (
            chartData.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-xs">
                <History className="w-8 h-8 text-slate-600 mb-2" />
                <span>No telemetry or irrigation records logged yet for this zone.</span>
                <span className="text-slate-600 mt-1">Apply manual water or step the simulation day to log dynamics.</span>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 15, right: 25, left: 0, bottom: 20 }}>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="timeLabel"
                        stroke="#64748b"
                        tick={{ fontSize: 10 }}
                        angle={-20}
                        textAnchor="end"
                        height={40}
                      />
                      <YAxis
                        yAxisId="left"
                        stroke="#38bdf8"
                        tick={{ fontSize: 10 }}
                        unit="%"
                        domain={[
                          0,
                          Math.max(35, Math.ceil((selectedZone.field_capacity_pct ?? 30) + 8)),
                        ]}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        stroke="#0ea5e9"
                        tick={{ fontSize: 10 }}
                        unit="mm"
                        domain={[0, 'auto']}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          borderRadius: '0.75rem',
                          fontSize: '11px',
                          color: '#f8fafc',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                      <ReferenceLine
                        yAxisId="left"
                        y={selectedZone.field_capacity_pct ?? 30}
                        stroke="#10b981"
                        strokeDasharray="4 4"
                        label={{
                          value: `FC (${selectedZone.field_capacity_pct ?? 30}%)`,
                          fill: '#10b981',
                          fontSize: 10,
                          position: 'insideTopLeft',
                        }}
                      />
                      <ReferenceLine
                        yAxisId="left"
                        y={selectedZone.wilting_point_pct ?? 12}
                        stroke="#ef4444"
                        strokeDasharray="4 4"
                        label={{
                          value: `WP (${selectedZone.wilting_point_pct ?? 12}%)`,
                          fill: '#ef4444',
                          fontSize: 10,
                          position: 'insideBottomLeft',
                        }}
                      />
                      <Bar
                        yAxisId="right"
                        dataKey="irrigationMm"
                        fill="#0284c7"
                        name="Applied Irrigation (mm)"
                        barSize={18}
                        radius={[4, 4, 0, 0]}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="moisture"
                        stroke="#38bdf8"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: '#0284c7' }}
                        activeDot={{ r: 6 }}
                        name="Soil Moisture (%)"
                        connectNulls
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-500 px-2 pt-1 border-t border-slate-800/60">
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                    Field Capacity: {selectedZone.field_capacity_pct ?? 30}% (Storage limit)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-400 inline-block" />
                    Wilting Point: {selectedZone.wilting_point_pct ?? 12}% (Plant stress threshold)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block" />
                    Current Moisture: {selectedZone.latest_soil_moisture_pct?.toFixed(1) ?? '22.0'}%
                  </span>
                </div>
              </div>
            )
          ) : (
            <div className="overflow-x-auto">
              {irrigationHistory.length === 0 ? (
                <div className="h-40 flex flex-col items-center justify-center text-slate-500 text-xs">
                  <span>No irrigation events recorded for this zone yet.</span>
                </div>
              ) : (
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-[10px] uppercase text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">Decision</th>
                      <th className="py-2.5 px-3">Depth (mm)</th>
                      <th className="py-2.5 px-3">Moisture Impact</th>
                      <th className="py-2.5 px-3">Duration</th>
                      <th className="py-2.5 px-3">Method</th>
                      <th className="py-2.5 px-3">Reasoning / Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {irrigationHistory.map((rec) => (
                      <tr key={rec.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 font-sans text-slate-400">
                          {rec.scheduled_at
                            ? new Date(rec.scheduled_at).toLocaleString(undefined, {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })
                            : '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold font-sans ${
                              rec.decision === 'MANUAL_COMMAND'
                                ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30'
                                : rec.decision === 'REQUIRED'
                                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                : rec.decision === 'POSTPONED'
                                ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                                : 'bg-slate-800 text-slate-400 border border-slate-700'
                            }`}
                          >
                            {rec.decision}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-slate-200">
                          {rec.actual_volume_mm !== null && rec.actual_volume_mm !== undefined
                            ? `${rec.actual_volume_mm.toFixed(1)} mm`
                            : rec.recommended_volume_mm !== null && rec.recommended_volume_mm !== undefined
                            ? `${rec.recommended_volume_mm.toFixed(1)} mm`
                            : '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          {rec.soil_moisture_before_pct !== null && rec.soil_moisture_before_pct !== undefined ? (
                            <span>
                              {rec.soil_moisture_before_pct}%{' '}
                              {rec.soil_moisture_after_pct !== null && rec.soil_moisture_after_pct !== undefined && (
                                <>
                                  &rarr;{' '}
                                  <span className="text-emerald-400 font-bold">
                                    {rec.soil_moisture_after_pct}%
                                  </span>
                                </>
                              )}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 font-sans">
                          {rec.actual_duration_min
                            ? `${rec.actual_duration_min} min`
                            : rec.recommended_duration_min
                            ? `${rec.recommended_duration_min} min`
                            : '—'}
                        </td>
                        <td className="py-2.5 px-3 capitalize font-sans text-slate-400">
                          {rec.irrigation_method || 'drip'}
                        </td>
                        <td className="py-2.5 px-3 font-sans text-slate-400 max-w-xs truncate" title={rec.reasoning_summary || ''}>
                          {rec.reasoning_summary || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* Manual Water Application Modal */}
      {manualModalOpen && selectedZone && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-scaleIn">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-sky-500/10 border border-sky-500/20 rounded-xl">
                  <Droplets className="w-5 h-5 text-sky-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">Manual Irrigation Application</h3>
                  <p className="text-xs text-slate-400">Target: {selectedZone.name} ({selectedZone.area_ha} ha)</p>
                </div>
              </div>
              <button
                onClick={() => setManualModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 text-lg"
              >
                ✕
              </button>
            </div>

            {/* Input Mode Selector */}
            <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800">
              <button
                type="button"
                onClick={() => setVolumeMode('mm')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition ${
                  volumeMode === 'mm' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Depth (mm)
              </button>
              <button
                type="button"
                onClick={() => setVolumeMode('liters')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition ${
                  volumeMode === 'liters' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Volume (Liters)
              </button>
            </div>

            {/* Form Fields */}
            <div className="space-y-4">
              {volumeMode === 'mm' ? (
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Irrigation Depth:</span>
                    <span className="font-bold text-sky-300">{irrigationDepthMm} mm</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="80"
                    step="0.5"
                    value={irrigationDepthMm}
                    onChange={(e) => handleDepthChange(Number(e.target.value))}
                    className="w-full accent-sky-500"
                  />
                  <div className="text-[11px] text-slate-500 mt-1 flex justify-between">
                    <span>Equivalent Volume:</span>
                    <span className="text-slate-300 font-medium">
                      {irrigationVolumeLiters.toLocaleString()} Liters ({selectedZone.area_ha} ha)
                    </span>
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Volume in Liters:</label>
                  <input
                    type="number"
                    min="1000"
                    max="1000000"
                    step="1000"
                    value={irrigationVolumeLiters}
                    onChange={(e) => handleVolumeChange(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-100"
                  />
                  <div className="text-[11px] text-slate-500 mt-1 flex justify-between">
                    <span>Equivalent Depth:</span>
                    <span className="text-slate-300 font-medium">{irrigationDepthMm} mm</span>
                  </div>
                </div>
              )}

              {/* Method Selector */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">Application Method:</label>
                <select
                  value={selectedMethod}
                  onChange={(e) => setSelectedMethod(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200"
                >
                  <option value="drip">Drip Irrigation (90% Application Efficiency)</option>
                  <option value="sprinkler">Sprinkler Irrigation (80% Application Efficiency)</option>
                  <option value="flood">Flood / Surface Irrigation (65% Application Efficiency)</option>
                </select>
              </div>

              {/* Flow Rate & Pumping Duration */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Pumping Flow Rate (L/h):</label>
                  <input
                    type="number"
                    min="5000"
                    max="100000"
                    step="1000"
                    value={flowRateLh}
                    onChange={(e) => setFlowRateLh(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Estimated Pumping Duration:</label>
                  <div className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-sky-300 font-semibold flex items-center h-9">
                    {calculatedDurationMinutes} min ({(calculatedDurationMinutes / 60).toFixed(1)} hrs)
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setManualModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setManualModalOpen(false);
                  handleApplyManualIrrigation();
                }}
                disabled={actionLoading}
                className="px-5 py-2.5 rounded-xl text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white shadow-lg shadow-sky-950 transition disabled:opacity-50"
              >
                {actionLoading ? 'Applying...' : 'Confirm & Apply Water'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Multi-Day Scenario Studio Modal */}
      {batchModalOpen && selectedFarm && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 animate-scaleIn">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                  <Sliders className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">Multi-Day Scenario Studio</h3>
                  <p className="text-xs text-slate-400">
                    Farm: <span className="text-slate-200 font-medium">{selectedFarm.name}</span> •{' '}
                    {allZones.length} Active Zones
                  </p>
                </div>
              </div>
              <button
                onClick={() => setBatchModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 text-lg"
              >
                ✕
              </button>
            </div>

            {/* Duration Selector */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Simulation Horizon (Days):
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[3, 7, 14, 30].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setBatchDays(d)}
                    className={`py-2 text-xs font-bold rounded-xl border transition ${
                      batchDays === d
                        ? 'bg-emerald-600 border-emerald-500 text-white shadow-lg shadow-emerald-950'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    {d} Days
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3 pt-1">
                <input
                  type="range"
                  min="1"
                  max="60"
                  value={batchDays}
                  onChange={(e) => setBatchDays(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
                <span className="text-xs font-mono font-bold text-emerald-300 w-16 text-right">
                  {batchDays} days
                </span>
              </div>
            </div>

            {/* Scenario Archetype Selection */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Agricultural Scenario Archetype:
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                {/* 1. Drydown */}
                <button
                  type="button"
                  onClick={() => {
                    setBatchScenario('drydown');
                    setBatchRainMm(0);
                  }}
                  className={`p-3 rounded-xl border text-left transition space-y-1 ${
                    batchScenario === 'drydown'
                      ? 'bg-amber-950/40 border-amber-500/60 ring-1 ring-amber-500/50'
                      : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
                    <Sun className="w-3.5 h-3.5 text-amber-400" />
                    <span>Extreme Drydown</span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    0 mm rain, zero irrigation. Observe root-zone depletion toward Wilting Point.
                  </p>
                </button>

                {/* 2. Monsoon */}
                <button
                  type="button"
                  onClick={() => {
                    setBatchScenario('monsoon');
                    setBatchRainMm(15);
                  }}
                  className={`p-3 rounded-xl border text-left transition space-y-1 ${
                    batchScenario === 'monsoon'
                      ? 'bg-sky-950/40 border-sky-500/60 ring-1 ring-sky-500/50'
                      : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-sky-300">
                    <CloudRain className="w-3.5 h-3.5 text-sky-400" />
                    <span>Monsoon Rain</span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Consistent daily precipitation. Test FC saturation and deep percolation.
                  </p>
                </button>

                {/* 3. Auto-Refill */}
                <button
                  type="button"
                  onClick={() => setBatchScenario('auto-refill')}
                  className={`p-3 rounded-xl border text-left transition space-y-1 ${
                    batchScenario === 'auto-refill'
                      ? 'bg-emerald-950/40 border-emerald-500/60 ring-1 ring-emerald-500/50'
                      : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-300">
                    <Zap className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Autonomous Refill</span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Auto-irrigate zones whenever volumetric moisture falls below target threshold.
                  </p>
                </button>

                {/* 4. Custom */}
                <button
                  type="button"
                  onClick={() => setBatchScenario('custom')}
                  className={`p-3 rounded-xl border text-left transition space-y-1 ${
                    batchScenario === 'custom'
                      ? 'bg-purple-950/40 border-purple-500/60 ring-1 ring-purple-500/50'
                      : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-purple-300">
                    <Sliders className="w-3.5 h-3.5 text-purple-400" />
                    <span>Custom Controls</span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2">
                    Configure custom daily rainfall overrides and specific refill limits.
                  </p>
                </button>
              </div>
            </div>

            {/* Contextual Parameter Adjustment */}
            {(batchScenario === 'auto-refill' || batchScenario === 'custom') && (
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Auto-Refill Moisture Threshold:</span>
                    <span className="font-bold text-emerald-300">{batchAutoRefillPct}%</span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="28"
                    step="0.5"
                    value={batchAutoRefillPct}
                    onChange={(e) => setBatchAutoRefillPct(Number(e.target.value))}
                    className="w-full accent-emerald-500"
                  />
                  <span className="text-[10px] text-slate-500 block">
                    Any zone dropping below this threshold will automatically receive precision water refill.
                  </span>
                </div>

                {batchScenario === 'custom' && (
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Daily Rain Override (mm/day):</span>
                      <span className="font-bold text-sky-300">{batchRainMm} mm</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="1"
                      value={batchRainMm}
                      onChange={(e) => setBatchRainMm(Number(e.target.value))}
                      className="w-full accent-sky-500"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setBatchModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setBatchModalOpen(false);
                  handleBatchSimulation(batchDays, batchScenario);
                }}
                disabled={actionLoading}
                className="px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950 transition disabled:opacity-50 flex items-center gap-2"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>{actionLoading ? 'Simulating...' : `Run ${batchDays}-Day Simulation`}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Water Conservation Summary Board ─────────────────────────────── */}
      {selectedFarm && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center gap-3 border-b border-slate-800 pb-4 mb-5">
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
              <TrendingDown className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">Water Conservation Summary</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Aggregated water-use metrics, IWUE, and model-based savings estimate vs. conventional baseline
              </p>
            </div>
          </div>
          <WaterConservationBoard farmId={selectedFarm.id} />
        </div>
      )}

      {/* ── PPO Deep RL Policy vs Rule-Based Benchmark ───────────────────── */}
      {selectedFarm && (
        <PPOBenchmarkCard
          farmId={selectedFarm.id}
          selectedZoneMoisture={selectedZone?.latest_soil_moisture_pct}
          selectedCropName={selectedZone?.crop_name || 'Wheat'}
        />
      )}

      {/* FAO-56 Penman-Monteith Thermodynamic Breakdown Modal */}
      {selectedFarm && (
        <FAO56BreakdownModal
          open={et0ModalOpen}
          onClose={() => setEt0ModalOpen(false)}
          farmId={selectedFarm.id}
          farmName={selectedFarm.name}
          selectedCropName={selectedZone?.crop_name || 'Wheat'}
          selectedZoneName={selectedZone?.name}
        />
      )}
    </div>
  );
};

