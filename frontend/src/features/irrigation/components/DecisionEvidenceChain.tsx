import React from 'react';
import type { DetailedAgentState } from '../types';
import {
  GitCommit,
  CloudSun,
  Droplet,
  Sprout,
  ShieldCheck,
} from 'lucide-react';

interface Props {
  state: DetailedAgentState;
}

export const DecisionEvidenceChain: React.FC<Props> = ({ state }) => {
  const w = state.weather;
  const s = state.soil;
  const c = state.crop;
  const e = state.et0;
  const opt = state.optimization;
  const d = state.irrigation_decision;

  const et0 = e?.et0_reference_mm ?? 4.2;
  const kc = c?.crop_coefficient_kc ?? 1.0;
  const etc = e?.etc_mm ?? (et0 * kc);
  const sm = s?.soil_moisture_pct ?? 20;
  const wp = s?.wilting_point_pct ?? 14;
  const fc = s?.field_capacity_pct ?? 32;

  const steps = [
    {
      num: '01',
      title: 'Atmospheric Evaporative Demand',
      icon: <CloudSun className="w-4 h-4 text-sky-400" />,
      detail: `Ambient Temp ${w?.temperature_c ?? 25}°C, Humidity ${w?.humidity_pct ?? 50}%, Wind ${w?.wind_speed_ms ?? 2.5} m/s`,
      deduction: `FAO-56 Penman-Monteith ET₀ = ${et0.toFixed(2)} mm/day`,
      status: 'verified',
    },
    {
      num: '02',
      title: 'Phenological Crop Multiplier',
      icon: <Sprout className="w-4 h-4 text-emerald-400" />,
      detail: `Crop: ${c?.crop_type || 'Wheat'} at ${c?.growth_stage || 'development'} stage (Kc = ${kc.toFixed(2)})`,
      deduction: `Consumptive Crop Water Demand ETc = ${etc.toFixed(2)} mm/day`,
      status: 'verified',
    },
    {
      num: '03',
      title: 'Soil Hydrological Reservoir Deficit',
      icon: <Droplet className="w-4 h-4 text-amber-400" />,
      detail: `Current θ: ${sm.toFixed(1)}%, WP: ${wp.toFixed(1)}%, FC: ${fc.toFixed(1)}%`,
      deduction: sm < wp ? 'Desiccated soil below wilting point (Severe stress)' : sm > fc ? 'Saturated soil above field capacity (Over-wet)' : `Depletion deficit calculated against management allowed depletion (MAD)`,
      status: sm < wp ? 'alert' : 'verified',
    },
    {
      num: '04',
      title: 'Precipitation Offset & Forecast Check',
      icon: <CloudRainIcon className="w-4 h-4 text-indigo-400" />,
      detail: `Observed rain: ${w?.rainfall_mm ?? 0} mm, Forecast rain: ${w?.forecast_rainfall_7d_mm ?? 0} mm`,
      deduction: (w?.forecast_rainfall_7d_mm ?? 0) >= 10.0 ? 'Forecast rainfall exceeds threshold (10mm). Triggering postponement.' : 'Precipitation insufficient to replenish root zone.',
      status: (w?.forecast_rainfall_7d_mm ?? 0) >= 10.0 ? 'warning' : 'verified',
    },
    {
      num: '05',
      title: 'Deficit Optimization & Hydraulic Quota',
      icon: <ShieldCheck className="w-4 h-4 text-purple-400" />,
      detail: `Baseline required: ${(opt?.baseline_volume_mm ?? 15.0).toFixed(1)} mm`,
      deduction: `Optimized depth: ${(opt?.optimized_volume_mm ?? d?.recommended_volume_mm ?? 12.0).toFixed(1)} mm (${(opt?.water_saving_pct ?? 20.0).toFixed(1)}% water conserved)`,
      status: 'verified',
    },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="p-1.5 bg-amber-500/10 text-amber-400 rounded-lg">
          <GitCommit className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Deterministic Physical Causality Chain</h3>
          <p className="text-xs text-slate-400">
            Step-by-step agronomic derivation from raw environmental variables to final decision.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((s, idx) => (
          <div
            key={s.num}
            className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/40 border border-slate-800"
          >
            <div className="flex flex-col items-center">
              <span className="font-mono text-xs font-bold text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                {s.num}
              </span>
              {idx < steps.length - 1 && (
                <div className="w-px h-6 bg-slate-700 my-1" />
              )}
            </div>

            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                {s.icon}
                <span className="text-xs font-semibold text-slate-200">{s.title}</span>
              </div>
              <div className="text-[11px] text-slate-400">{s.detail}</div>
              <div className="mt-1 text-xs font-mono text-emerald-400 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
                ➔ {s.deduction}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const CloudRainIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
    <path d="M16 14v6" />
    <path d="M8 14v6" />
    <path d="M12 16v6" />
  </svg>
);
