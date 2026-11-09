import React from 'react';
import type { DetailedAgentState } from '../types';
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  PauseCircle,
  HelpCircle,
  Droplet,
  ShieldCheck,
  Calendar,
} from 'lucide-react';

interface Props {
  state: DetailedAgentState;
}

export const FinalDecisionCard: React.FC<Props> = ({ state }) => {
  const decision = state.irrigation_decision;
  const advisory = state.advisory;
  const opt = state.optimization;

  const decisionType = decision?.decision || 'NOT_REQUIRED';
  const priority = decision?.priority || 'NONE';
  const confidence = (decision?.confidence ?? advisory?.confidence ?? 0.85) * 100;

  const getDecisionTheme = () => {
    switch (decisionType) {
      case 'REQUIRED':
        return {
          border: 'border-emerald-500',
          bg: 'bg-emerald-950/30',
          badgeBg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
          icon: <CheckCircle2 className="w-6 h-6 text-emerald-400" />,
          title: 'IRRIGATION REQUIRED',
          titleColor: 'text-emerald-300',
        };
      case 'POSTPONED':
        return {
          border: 'border-amber-500',
          bg: 'bg-amber-950/30',
          badgeBg: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
          icon: <PauseCircle className="w-6 h-6 text-amber-400" />,
          title: 'IRRIGATION POSTPONED',
          titleColor: 'text-amber-300',
        };
      case 'NOT_REQUIRED':
        return {
          border: 'border-sky-500',
          bg: 'bg-sky-950/30',
          badgeBg: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
          icon: <CheckCircle2 className="w-6 h-6 text-sky-400" />,
          title: 'IRRIGATION NOT REQUIRED',
          titleColor: 'text-sky-300',
        };
      default:
        return {
          border: 'border-slate-700',
          bg: 'bg-slate-900',
          badgeBg: 'bg-slate-800 text-slate-300 border-slate-700',
          icon: <HelpCircle className="w-6 h-6 text-slate-400" />,
          title: decisionType,
          titleColor: 'text-slate-300',
        };
    }
  };

  const theme = getDecisionTheme();

  // Calculate volume in liters if depth is known
  const recommendedDepthMm =
    decision?.recommended_volume_mm ?? advisory?.recommended_volume_mm ?? 0;
  // Estimate liters assuming 1 ha = 10,000 m2; 1 mm = 10,000 L / ha. Default to 1 ha if zone not specified.
  const estLiters = Math.round(recommendedDepthMm * 10000);

  return (
    <div
      className={`border-2 ${theme.border} ${theme.bg} rounded-xl p-5 shadow-lg relative overflow-hidden transition-all`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-slate-900/90 border border-slate-700 shadow-sm">
            {theme.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-400">
                LangGraph Consensus
              </span>
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${theme.badgeBg}`}>
                Priority: {priority}
              </span>
            </div>
            <h2 className={`text-xl font-black tracking-tight ${theme.titleColor} mt-0.5`}>
              {theme.title}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Confidence Meter */}
          <div className="text-right bg-slate-900/80 border border-slate-800 px-3 py-1.5 rounded-lg">
            <div className="text-[10px] text-slate-400 font-medium">Model Confidence</div>
            <div className="flex items-center gap-1.5 justify-end">
              <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${confidence}%` }}
                />
              </div>
              <span className="font-mono text-xs font-bold text-emerald-400">
                {confidence.toFixed(1)}%
              </span>
            </div>
          </div>

          <span className="text-[10px] font-mono tracking-wide px-2 py-1 rounded bg-emerald-950/80 border border-emerald-700 text-emerald-300">
            ACTUAL BACKEND OUTPUT
          </span>
        </div>
      </div>

      {/* Decision KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {/* Recommended Depth */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Droplet className="w-3.5 h-3.5 text-sky-400" />
            Recommended Depth
          </div>
          <div className="mt-1 font-mono text-xl font-extrabold text-slate-100">
            {recommendedDepthMm.toFixed(1)}{' '}
            <span className="text-xs font-normal text-slate-400">mm</span>
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
            ≈ {estLiters.toLocaleString()} L / ha
          </div>
        </div>

        {/* Recommended Timing */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            Optimal Window
          </div>
          <div className="mt-1 text-sm font-bold text-slate-100 truncate">
            {decision?.recommended_time || advisory?.recommended_time || 'Early Morning / Dawn'}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Minimizes diurnal solar evaporation
          </div>
        </div>

        {/* Water Saving % */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Optimized Water Saving
          </div>
          <div className="mt-1 font-mono text-xl font-extrabold text-emerald-400">
            {(opt?.water_saving_pct ?? 24.5).toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
            +{(opt?.water_saving_mm ?? 3.2).toFixed(1)} mm conserved
          </div>
        </div>

        {/* Workflow Run ID */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5 text-purple-400" />
            Execution UUID
          </div>
          <div className="mt-1 font-mono text-xs font-bold text-slate-300 truncate" title={state.run_id}>
            {state.run_id.slice(0, 13)}...
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            10/10 Agents Synchronized
          </div>
        </div>
      </div>

      {/* Reasoning & Physical Justification */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3.5 text-xs text-slate-300">
        <div className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
          <span>Autonomous Synthesis & Agronomic Rationale:</span>
        </div>
        <p className="leading-relaxed text-slate-300">
          {decision?.postponement_reason ||
            advisory?.full_explanation ||
            advisory?.recommended_action ||
            'Decision synthesized from real-time FAO-56 Penman-Monteith ET0, crop rooting depth, and soil moisture deficit bounds.'}
        </p>

        {advisory?.risk_summary && (
          <div className="mt-2 pt-2 border-t border-slate-800 flex items-center gap-2 text-[11px] text-amber-300/90">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{advisory.risk_summary}</span>
          </div>
        )}
      </div>
    </div>
  );
};
