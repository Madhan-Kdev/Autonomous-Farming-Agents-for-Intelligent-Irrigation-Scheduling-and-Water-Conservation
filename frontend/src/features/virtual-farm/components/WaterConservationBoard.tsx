/**
 * WaterConservationBoard — Task 2.2
 *
 * Water Conservation Summary Board for the Virtual Farm tab.
 * Displays aggregated water-use metrics, Irrigation Water Use Efficiency (IWUE),
 * and estimated water savings versus a configurable conventional baseline.
 *
 * Data source: GET /api/v1/analytics/conservation-summary
 * All calculations are performed server-side — this component only renders.
 *
 * Labelling rules (master prompt §3):
 * - Conservation/savings figures marked as "SIMULATED MODEL-BASED ESTIMATE"
 * - Applied water marked "ACTUAL APPLIED"
 * - ETc demand marked "ETc DEMAND"
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Area,
} from 'recharts';
import {
  Droplets,
  Zap,
  TrendingDown,
  Leaf,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Info,
  Settings2,
} from 'lucide-react';
import type { ConservationSummary, DailyConservationPoint } from '../../../types';
import { fetchConservationSummary } from '../api';

interface WaterConservationBoardProps {
  farmId: number;
}

// ─── Custom tooltip for the trend chart ─────────────────────────────────────

interface TrendTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

const TrendTooltip: React.FC<TrendTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-xl">
      <p className="text-slate-300 font-bold mb-1.5">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full inline-block" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-bold text-slate-200">{p.value.toFixed(2)} mm</span>
        </div>
      ))}
    </div>
  );
};

// ─── Metric card ─────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  badge?: string;
  badgeColor?: string;
  icon: React.ReactNode;
  accent?: string;
  note?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  badge,
  badgeColor = 'text-slate-400 bg-slate-800',
  icon,
  accent = 'border-slate-800',
  note,
}) => (
  <div className={`bg-slate-950 border ${accent} p-4 rounded-2xl space-y-1.5 relative overflow-hidden`}>
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">{label}</span>
      {badge && (
        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${badgeColor}`}>
          {badge}
        </span>
      )}
    </div>
    <div className="flex items-end gap-1.5">
      <span className="text-2xl font-extrabold text-slate-100 font-mono leading-tight">{value}</span>
      {unit && <span className="text-xs text-slate-400 mb-0.5">{unit}</span>}
    </div>
    <div className="flex items-center gap-1.5 text-slate-500">
      <span className="w-3.5 h-3.5">{icon}</span>
      {note && <span className="text-[10px]">{note}</span>}
    </div>
  </div>
);

// ─── Decision badge ───────────────────────────────────────────────────────────

const DECISION_COLORS: Record<string, string> = {
  REQUIRED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  POSTPONED: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  NOT_REQUIRED: 'bg-slate-700/50 text-slate-400 border-slate-600',
  MANUAL_COMMAND: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  MANUAL: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
};

// ─── Main component ───────────────────────────────────────────────────────────

export const WaterConservationBoard: React.FC<WaterConservationBoardProps> = ({
  farmId,
}) => {
  const [summary, setSummary] = useState<ConservationSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [windowDays, setWindowDays] = useState<number>(14);
  const [conventionalMm, setConventionalMm] = useState<number>(6.0);
  const [showSettings, setShowSettings] = useState<boolean>(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchConservationSummary(farmId, windowDays, conventionalMm);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load water conservation data');
    } finally {
      setLoading(false);
    }
  }, [farmId, windowDays, conventionalMm]);

  useEffect(() => {
    load();
  }, [load]);

  // Format numbers safely
  const fmt = (n: number, dec = 1) =>
    isNaN(n) ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: dec });

  // Shorten date labels for the chart
  const formatDate = (d: string) => {
    const dt = new Date(d);
    return `${dt.getDate()}/${dt.getMonth() + 1}`;
  };

  if (loading) {
    return (
      <div className="h-72 flex flex-col items-center justify-center gap-3 text-slate-400">
        <div className="w-7 h-7 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs">Aggregating water conservation metrics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-950/40 border border-red-500/30 rounded-2xl text-xs text-red-300 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
        <button onClick={load} className="ml-auto text-red-400 underline">Retry</button>
      </div>
    );
  }

  if (!summary) return null;

  const trendData = summary.daily_trend.map((pt: DailyConservationPoint) => ({
    ...pt,
    date_label: formatDate(pt.date),
  }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <Leaf className="w-4 h-4 text-emerald-400" />
            Water Conservation Board
            <span className="text-[10px] font-normal text-slate-500">
              {summary.window_start} → {summary.window_end}
            </span>
          </h4>
          <p className="text-[11px] text-slate-500 mt-0.5">{summary.farm_name}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            title="Configure baseline"
          >
            <Settings2 className="w-4 h-4" />
          </button>
          <button
            onClick={load}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3 text-xs">
          <span className="font-semibold text-slate-300 block">Analysis Settings</span>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-slate-400">Rolling Window (days)</label>
              <input
                type="number"
                min={3}
                max={90}
                value={windowDays}
                onChange={(e) => setWindowDays(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200"
              />
            </div>
            <div className="space-y-1">
              <label className="text-slate-400">Conventional Baseline (mm/day)</label>
              <input
                type="number"
                min={1}
                max={30}
                step={0.5}
                value={conventionalMm}
                onChange={(e) => setConventionalMm(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200"
              />
            </div>
          </div>
          <button
            onClick={() => { setShowSettings(false); load(); }}
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-semibold transition"
          >
            Apply
          </button>
        </div>
      )}

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Water Applied"
          value={fmt(summary.total_water_applied_mm)}
          unit="mm"
          badge="ACTUAL APPLIED"
          badgeColor="text-sky-300 bg-sky-500/10"
          icon={<Droplets className="w-3.5 h-3.5 text-sky-400" />}
          accent="border-sky-500/20"
          note={`${(summary.total_water_applied_liters / 1000).toFixed(1)} kL total`}
        />
        <MetricCard
          label="ETc Crop Demand"
          value={fmt(summary.total_etc_demand_mm)}
          unit="mm"
          badge="ETc DEMAND"
          badgeColor="text-amber-300 bg-amber-500/10"
          icon={<Zap className="w-3.5 h-3.5 text-amber-400" />}
          accent="border-amber-500/20"
          note="Crop water requirement"
        />
        <MetricCard
          label="IWUE"
          value={fmt(summary.iwue, 2)}
          unit="ETc/mm"
          badge="EFFICIENCY"
          badgeColor="text-purple-300 bg-purple-500/10"
          icon={<CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />}
          accent="border-purple-500/20"
          note={summary.iwue >= 1 ? 'Rain assisted' : summary.iwue > 0 ? 'Over-irrigation risk' : 'No data'}
        />
        <MetricCard
          label="Water Saved"
          value={fmt(summary.water_saved_pct, 1)}
          unit="%"
          badge="SIMULATED EST."
          badgeColor="text-emerald-300 bg-emerald-500/10"
          icon={<TrendingDown className="w-3.5 h-3.5 text-emerald-400" />}
          accent="border-emerald-500/20"
          note={`vs ${summary.conventional_daily_mm} mm/day baseline`}
        />
      </div>

      {/* Water savings bar */}
      <div className="p-4 bg-slate-950 border border-emerald-500/20 rounded-2xl space-y-2">
        <div className="flex justify-between text-xs">
          <span className="font-semibold text-slate-300">
            Intelligent vs. Conventional Water Use
            <span className="ml-2 text-[10px] font-normal text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
              SIMULATED MODEL-BASED ESTIMATE
            </span>
          </span>
          <span className="text-slate-400">
            {fmt(summary.total_water_applied_mm)} mm applied vs {fmt(summary.conventional_total_mm)} mm conventional
          </span>
        </div>
        <div className="relative h-5 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
          <div
            className="absolute left-0 top-0 h-full bg-sky-500 transition-all duration-700"
            style={{ width: `${Math.min((summary.total_water_applied_mm / Math.max(summary.conventional_total_mm, 1)) * 100, 100)}%` }}
          />
          <div className="absolute right-0 top-0 h-full bg-emerald-500/30 transition-all duration-700"
            style={{ width: `${Math.min(summary.water_saved_pct, 100)}%` }}
          />
        </div>
        <div className="flex gap-4 text-[10px] text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sky-500 inline-block" /> Intelligent system applied</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500/50 inline-block" /> Estimated savings</span>
        </div>
      </div>

      {/* Decision breakdown */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        {[
          { label: 'Required', count: summary.decisions_required, cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20' },
          { label: 'Postponed', count: summary.decisions_postponed, cls: 'text-amber-300 bg-amber-500/10 border-amber-500/20' },
          { label: 'Not Required', count: summary.decisions_not_required, cls: 'text-slate-400 bg-slate-800/50 border-slate-700' },
          { label: 'Manual', count: summary.decisions_manual, cls: 'text-blue-300 bg-blue-500/10 border-blue-500/20' },
        ].map(({ label, count, cls }) => (
          <div key={label} className={`p-3 rounded-xl border text-center ${cls}`}>
            <span className="text-xl font-extrabold font-mono block">{count}</span>
            <span className="text-[10px] opacity-80">{label}</span>
          </div>
        ))}
      </div>

      {/* Daily Trend Chart */}
      {trendData.length > 0 && (
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <div className="flex justify-between items-center text-xs">
            <span className="font-semibold text-slate-300">Daily Water Use Trend</span>
            <span className="text-[10px] text-slate-500">{windowDays}-day rolling window</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={trendData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="date_label"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#1e293b' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#1e293b' }}
                tickLine={false}
                unit=" mm"
              />
              <Tooltip content={<TrendTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 10, color: '#94a3b8', paddingTop: 8 }}
                iconSize={8}
              />
              {/* Conventional baseline area */}
              <Area
                type="monotone"
                dataKey="conventional_mm"
                name="Conventional baseline"
                fill="#f59e0b22"
                stroke="#f59e0b55"
                strokeDasharray="4 2"
                dot={false}
                activeDot={false}
              />
              {/* ETc demand line */}
              <Line
                type="monotone"
                dataKey="etc_demand_mm"
                name="ETc demand"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
              />
              {/* Precipitation */}
              <Bar dataKey="precipitation_mm" name="Precipitation" fill="#38bdf8" opacity={0.6} barSize={6} />
              {/* Applied water */}
              <Bar dataKey="water_applied_mm" name="Water applied" fill="#34d399" barSize={6} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Disclaimer */}
      <div className="p-3 bg-amber-950/20 border border-amber-500/20 rounded-xl flex gap-2 text-[10px] text-amber-400/80">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
        <span>{summary.disclaimer}</span>
      </div>
    </div>
  );
};

