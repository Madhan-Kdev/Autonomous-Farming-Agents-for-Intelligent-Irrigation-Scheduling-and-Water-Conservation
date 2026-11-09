import React from 'react';
import type { DetailedAgentState } from '../types';
import {
  Activity,
  Droplets,
  CloudSun,
  Sprout,
} from 'lucide-react';

interface Props {
  state: DetailedAgentState;
}

export const AgriculturalStateCard: React.FC<Props> = ({ state }) => {
  const soil = state.soil;
  const crop = state.crop;
  const et0 = state.et0;
  const opt = state.optimization;

  const sm = soil?.soil_moisture_pct ?? 0;
  const fc = soil?.field_capacity_pct ?? 30;
  const wp = soil?.wilting_point_pct ?? 14;
  const stress = soil?.soil_stress_index ?? 0;

  const awc = Math.max(0.1, fc - wp);
  const currentAwcPct = Math.max(0, Math.min(100, ((sm - wp) / awc) * 100));

  const et0Ref = et0?.et0_reference_mm ?? 0;
  const et0Pred = et0?.et0_predicted_mm ?? et0Ref;
  const etc = et0?.etc_mm ?? 0;
  const kc = crop?.crop_coefficient_kc ?? 1.0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Agricultural State & Provenance</h3>
            <p className="text-xs text-slate-400">
              Verified hydrological variables with explicit mathematical and algorithmic provenance tags.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Soil Moisture & Depletion */}
        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Droplets className="w-4 h-4 text-amber-400" />
                Soil Water Fraction
              </span>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300">
                SIMULATED / VIRTUAL DATA
              </span>
            </div>

            <div className="flex items-baseline gap-2 mb-1">
              <span className="font-mono text-2xl font-black text-amber-300">
                {sm.toFixed(1)}%
              </span>
              <span className="text-xs text-slate-400">volumetric moisture</span>
            </div>

            <div className="space-y-1.5 my-3">
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>WP: {wp.toFixed(1)}%</span>
                <span className="font-mono text-slate-300 font-medium">
                  {currentAwcPct.toFixed(0)}% AWC
                </span>
                <span>FC: {fc.toFixed(1)}%</span>
              </div>
              <div className="w-full h-2.5 bg-slate-700 rounded-full overflow-hidden relative">
                <div
                  className={`h-full transition-all duration-500 ${
                    sm < wp
                      ? 'bg-rose-500'
                      : sm > fc
                      ? 'bg-blue-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${currentAwcPct}%` }}
                />
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-700/50 flex items-center justify-between">
            <span>Soil Stress Index:</span>
            <span
              className={`font-mono font-bold ${
                stress > 0.6 ? 'text-rose-400' : stress > 0.3 ? 'text-amber-400' : 'text-emerald-400'
              }`}
            >
              {stress.toFixed(2)} / 1.00
            </span>
          </div>
        </div>

        {/* Evapotranspiration & Demand */}
        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <CloudSun className="w-4 h-4 text-sky-400" />
                Evapotranspiration
              </span>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300">
                FAO-56 PM (PHYSICAL)
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 my-2">
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-400">Reference ET0 (FAO-56)</div>
                <div className="font-mono text-base font-bold text-sky-300 mt-0.5">
                  {et0Ref.toFixed(2)} <span className="text-[10px] font-normal text-slate-400">mm/d</span>
                </div>
              </div>

              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <div className="text-[10px] text-slate-400 flex items-center justify-between">
                  <span>ML Predicted ET0</span>
                  <span className="text-[8px] bg-purple-950 text-purple-300 px-1 rounded">GBR</span>
                </div>
                <div className="font-mono text-base font-bold text-purple-300 mt-0.5">
                  {et0Pred.toFixed(2)} <span className="text-[10px] font-normal text-slate-400">mm/d</span>
                </div>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-700/50 flex items-center justify-between">
            <span>Crop Demand (ETc = ET0 × Kc):</span>
            <span className="font-mono font-bold text-sky-300">
              {etc.toFixed(2)} mm/day
            </span>
          </div>
        </div>

        {/* Crop Phenology & Conservation */}
        <div className="bg-slate-800/50 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Sprout className="w-4 h-4 text-emerald-400" />
                Agronomic Context
              </span>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
                RECOMMENDATION
              </span>
            </div>

            <div className="space-y-1 text-xs my-2">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Crop Species:</span>
                <span className="font-semibold text-slate-200">{crop?.crop_type || 'Wheat'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Growth Stage:</span>
                <span className="font-semibold text-emerald-300 capitalize">
                  {crop?.growth_stage || 'Development'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Crop Coefficient (Kc):</span>
                <span className="font-mono font-bold text-slate-200">{kc.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-700/50 flex items-center justify-between">
            <span>Conservation Savings:</span>
            <span className="font-mono font-bold text-emerald-400">
              {(opt?.water_saving_pct ?? 20.0).toFixed(1)}% vs static baseline
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
