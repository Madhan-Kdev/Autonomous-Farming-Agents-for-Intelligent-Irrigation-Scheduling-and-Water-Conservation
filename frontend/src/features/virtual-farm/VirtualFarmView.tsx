import React, { useState, useEffect } from 'react';
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
  Waves
} from 'lucide-react';
import type { Farm, Zone, ManualIrrigationOut, SimulationStepOut } from '../../types';
import {
  fetchFarmDigitalTwin,
  fetchAllFarms,
  applyManualIrrigation,
  advanceSimulationDay
} from './api';

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

  useEffect(() => {
    loadFarms();
  }, []);

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
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-xl text-sm font-medium transition disabled:opacity-50"
          >
            <Calendar className="w-4 h-4 text-sky-400" />
            <span>Step 1 Day</span>
          </button>

          <button
            onClick={() => handleAdvanceDay(3, 0.0)}
            disabled={actionLoading}
            className="flex items-center gap-2 bg-amber-950/60 hover:bg-amber-900/60 border border-amber-600/40 text-amber-300 px-4 py-2 rounded-xl text-sm font-medium transition disabled:opacity-50"
            title="Advance 3 days with zero rainfall to simulate drought drydown"
          >
            <TrendingDown className="w-4 h-4 text-amber-400" />
            <span>Simulate 3-Day Drydown</span>
          </button>
        </div>
      </div>

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
              <span className="flex items-center gap-1.5">
                <CloudSun className="w-4 h-4 text-amber-400" />
                <span>Simulated ET₀: {lastSimulationStep?.simulated_et0_mm?.toFixed(1) || '4.2'} mm/day</span>
              </span>
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
                    {selectedZone.area_ha} Hectares
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
    </div>
  );
};

