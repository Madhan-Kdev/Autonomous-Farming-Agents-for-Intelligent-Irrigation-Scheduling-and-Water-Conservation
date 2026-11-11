/**
 * PPOBenchmarkCard — Task 3.1
 *
 * Deep Reinforcement Learning (PPO) vs Classical Rule-Based Decision Benchmarking.
 * Evaluates state under Gymnasium environment dynamics and compares policy output
 * against the deterministic FAO-56 rules engine.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Cpu,
  Scale,
  Zap,
  TrendingDown,
  CloudRain,
  Droplets,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Sliders,
  RefreshCw,
  Info,
} from 'lucide-react';
import type { PolicyComparisonOut, RLBenchmarkRequest } from '../../../types';
import { benchmarkRLPolicy } from '../api';

interface PPOBenchmarkCardProps {
  farmId: number;
  selectedZoneMoisture?: number | null;
  selectedCropName?: string;
}

const ALIGNMENT_BADGES = {
  AGREE: {
    label: 'Fully Aligned',
    color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  },
  DEFICIT_SAVINGS: {
    label: 'PPO Deficit Savings',
    color: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  },
  RAIN_HARVEST: {
    label: 'Rain Suppression',
    color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  },
  DIVERGENT: {
    label: 'Policy Divergence',
    color: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  },
};

export const PPOBenchmarkCard: React.FC<PPOBenchmarkCardProps> = ({
  farmId,
  selectedZoneMoisture,
  selectedCropName = 'Wheat',
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [comparison, setComparison] = useState<PolicyComparisonOut | null>(null);

  // Scenario simulator inputs
  const [soilMoisture, setSoilMoisture] = useState<number>(selectedZoneMoisture ?? 18.5);
  const [fieldCapacity, setFieldCapacity] = useState<number>(30.0);
  const [wiltingPoint, setWiltingPoint] = useState<number>(12.0);
  const [etcMm, setEtcMm] = useState<number>(5.5);
  const [forecastRainMm, setForecastRainMm] = useState<number>(0.0);
  const [tempC, setTempC] = useState<number>(28.0);
  const [growthStage, setGrowthStage] = useState<string>('mid');
  const [showControls, setShowControls] = useState<boolean>(false);

  useEffect(() => {
    if (selectedZoneMoisture !== undefined && selectedZoneMoisture !== null) {
      setSoilMoisture(selectedZoneMoisture);
    }
  }, [selectedZoneMoisture]);

  const runBenchmark = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const req: RLBenchmarkRequest = {
        farm_id: farmId,
        soil_moisture_pct: soilMoisture,
        field_capacity_pct: fieldCapacity,
        wilting_point_pct: wiltingPoint,
        et0_mm: etcMm * 0.9,
        etc_mm: etcMm,
        forecast_rain_mm: forecastRainMm,
        temperature_c: tempC,
        growth_stage: growthStage,
        crop_name: selectedCropName,
      };
      const res = await benchmarkRLPolicy(req);
      setComparison(res);
    } catch (err: any) {
      setError(err.message || 'Failed to benchmark PPO policy');
    } finally {
      setLoading(false);
    }
  }, [farmId, soilMoisture, fieldCapacity, wiltingPoint, etcMm, forecastRainMm, tempC, growthStage, selectedCropName]);

  useEffect(() => {
    runBenchmark();
  }, [runBenchmark]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-xl">
            <Cpu className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-100">
                PPO Deep RL vs. Rule-Based Decision Benchmark
              </h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Gymnasium DRL Policy
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Side-by-side comparative evaluation of trained PPO Actor-Critic policy versus classical FAO-56 water balance rules
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowControls(!showControls)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>{showControls ? 'Hide Controls' : 'Simulate Scenarios'}</span>
          </button>
          <button
            onClick={runBenchmark}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
            title="Refresh Benchmark"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Interactive Controls Drawer */}
      {showControls && (
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-4 text-xs animate-fadeIn">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-200 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Scenario State Variables
            </span>
            <span className="text-[10px] text-slate-500">
              Adjust parameters to test policy generalization
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <div className="flex justify-between text-slate-400">
                <span>Soil Moisture (&theta;):</span>
                <span className="font-bold text-slate-200">{soilMoisture.toFixed(1)}%</span>
              </div>
              <input
                type="range"
                min="8"
                max="35"
                step="0.5"
                value={soilMoisture}
                onChange={(e) => setSoilMoisture(Number(e.target.value))}
                className="w-full accent-purple-500"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-slate-400">
                <span>Forecast Rain:</span>
                <span className="font-bold text-sky-300">{forecastRainMm.toFixed(1)} mm</span>
              </div>
              <input
                type="range"
                min="0"
                max="40"
                step="1"
                value={forecastRainMm}
                onChange={(e) => setForecastRainMm(Number(e.target.value))}
                className="w-full accent-sky-500"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-slate-400">
                <span>Daily Crop ETc:</span>
                <span className="font-bold text-amber-300">{etcMm.toFixed(1)} mm/d</span>
              </div>
              <input
                type="range"
                min="2"
                max="12"
                step="0.5"
                value={etcMm}
                onChange={(e) => setEtcMm(Number(e.target.value))}
                className="w-full accent-amber-500"
              />
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="h-48 flex flex-col items-center justify-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs">Evaluating PPO actor-critic network and rule engine...</span>
        </div>
      ) : comparison ? (
        <div className="space-y-5">
          {/* Alignment Banner */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span
                className={`text-xs font-bold px-3 py-1 rounded-xl border ${
                  ALIGNMENT_BADGES[comparison.alignment]?.color || 'bg-slate-800 text-slate-300'
                }`}
              >
                {ALIGNMENT_BADGES[comparison.alignment]?.label || comparison.alignment}
              </span>
              <p className="text-xs text-slate-300 font-medium">
                {comparison.synthesis}
              </p>
            </div>

            {comparison.water_savings_vs_rule_pct > 0 && (
              <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-xl text-xs text-emerald-300 font-bold">
                <TrendingDown className="w-4 h-4" />
                <span>{comparison.water_savings_vs_rule_pct.toFixed(1)}% PPO Water Savings</span>
              </div>
            )}
          </div>

          {/* Side-by-Side Comparison Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Rule-Based Card */}
            <div className="bg-slate-950 border border-slate-800 p-5 rounded-2xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2">
                  <Scale className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-bold text-slate-200">
                    Classical FAO-56 Rules Engine
                  </span>
                </div>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                  Deterministic
                </span>
              </div>

              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-400 block">Recommended Action</span>
                  <span className="text-2xl font-extrabold text-slate-100 font-mono">
                    {comparison.rule_decision.recommended_volume_mm.toFixed(1)}{' '}
                    <span className="text-xs text-slate-400 font-normal">mm</span>
                  </span>
                </div>
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-lg ${
                    comparison.rule_decision.decision === 'REQUIRED'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {comparison.rule_decision.decision}
                </span>
              </div>

              <div className="space-y-1 text-xs text-slate-400">
                <p className="line-clamp-2">{comparison.rule_decision.rationale}</p>
                <div className="flex items-center gap-2 pt-2 text-[11px] text-slate-500">
                  <span>Priority: {comparison.rule_decision.priority}</span>
                  <span>&bull;</span>
                  <span>Confidence: {(comparison.rule_decision.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>

            {/* PPO Policy Card */}
            <div className="bg-slate-950 border border-purple-500/30 p-5 rounded-2xl space-y-3 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-2xl pointer-events-none" />

              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-bold text-purple-200">
                    PPO Deep RL Policy Network
                  </span>
                </div>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  Actor-Critic
                </span>
              </div>

              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-slate-400 block">Optimal Policy Action</span>
                  <span className="text-2xl font-extrabold text-purple-300 font-mono">
                    {comparison.ppo_policy.action_mm.toFixed(1)}{' '}
                    <span className="text-xs text-slate-400 font-normal">mm</span>
                  </span>
                </div>
                <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-purple-500/20 text-purple-300">
                  {comparison.ppo_policy.action_name}
                </span>
              </div>

              {/* Action Probability Distribution */}
              <div className="space-y-1.5 pt-1">
                <span className="text-[11px] text-slate-400 block">
                  Action Softmax Distribution:
                </span>
                <div className="grid grid-cols-5 gap-1.5 text-center">
                  {Object.entries(comparison.ppo_policy.action_probabilities).map(([act, p]) => (
                    <div
                      key={act}
                      className={`p-1.5 rounded-lg border text-[10px] font-mono ${
                        act === `${Math.round(comparison.ppo_policy.action_mm)}mm`
                          ? 'bg-purple-600/30 border-purple-500 text-purple-200 font-bold'
                          : 'bg-slate-900 border-slate-800 text-slate-400'
                      }`}
                    >
                      <div className="text-[9px] text-slate-500">{act}</div>
                      <div>{(p * 100).toFixed(0)}%</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="text-[11px] text-slate-400 pt-1">
                <p>{comparison.ppo_policy.rationale}</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
