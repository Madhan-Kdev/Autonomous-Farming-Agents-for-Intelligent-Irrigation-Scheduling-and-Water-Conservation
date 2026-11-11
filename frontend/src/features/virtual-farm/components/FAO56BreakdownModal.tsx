import React, { useState, useEffect } from 'react';
import {
  X,
  CloudSun,
  Wind,
  Droplets,
  Sun,
  Activity,
  Calculator,
  Sliders,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Sparkles,
  RotateCcw,
} from 'lucide-react';
import type { ET0DerivationOut, CalculateET0Request } from '../../../types';
import { fetchET0Derivation, calculateCustomET0 } from '../api';

interface FAO56BreakdownModalProps {
  open: boolean;
  onClose: () => void;
  farmId: number;
  farmName?: string;
  selectedCropName?: string;
  selectedZoneName?: string;
}

export const FAO56BreakdownModal: React.FC<FAO56BreakdownModalProps> = ({
  open,
  onClose,
  farmId,
  farmName = 'Demo Farm',
  selectedCropName = 'Wheat',
  selectedZoneName,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'steps' | 'simulator'>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [derivation, setDerivation] = useState<ET0DerivationOut | null>(null);

  // Crop ETc stage controls
  const [selectedCrop, setSelectedCrop] = useState<string>(selectedCropName);
  const [growthStage, setGrowthStage] = useState<'initial' | 'development' | 'mid' | 'late'>('mid');

  // Interactive Simulator State
  const [simTempMax, setSimTempMax] = useState<number>(32.0);
  const [simTempMin, setSimTempMin] = useState<number>(20.0);
  const [simRhMax, setSimRhMax] = useState<number>(80.0);
  const [simRhMin, setSimRhMin] = useState<number>(35.0);
  const [simWindSpeed, setSimWindSpeed] = useState<number>(2.5);
  const [simSolarRad, setSimSolarRad] = useState<number>(22.0);
  const [simAltitude, setSimAltitude] = useState<number>(100.0);
  const [simulating, setSimulating] = useState<boolean>(false);

  // Accordion open state for 13 steps
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (open) {
      loadLiveDerivation();
    }
  }, [open, farmId, selectedCrop, growthStage]);

  const loadLiveDerivation = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchET0Derivation(farmId, selectedCrop, growthStage);
      setDerivation(data);
      // Initialize simulator with live values
      setSimTempMax(Math.round(data.t_mean_c + 6));
      setSimTempMin(Math.round(data.t_mean_c - 6));
      setSimWindSpeed(data.wind_speed_m_s);
      setSimSolarRad(data.solar_radiation_mj_m2);
      setSimAltitude(Math.round(((101.3 - data.pressure_kpa) / 101.3) * 8500));
    } catch (err: any) {
      setError(err.message || 'Failed to load FAO-56 derivation');
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulator = async () => {
    setSimulating(true);
    setError('');
    try {
      const req: CalculateET0Request = {
        temp_max_c: simTempMax,
        temp_min_c: simTempMin,
        humidity_max_pct: simRhMax,
        humidity_min_pct: simRhMin,
        wind_speed_m_s: simWindSpeed,
        solar_radiation_mj_m2: simSolarRad,
        altitude_m: simAltitude,
        latitude_deg: 18.52,
        crop_name: selectedCrop,
        growth_stage: growthStage,
      };
      const data = await calculateCustomET0(req);
      setDerivation(data);
    } catch (err: any) {
      setError(err.message || 'Simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  const toggleStep = (stepNumber: number) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepNumber]: !prev[stepNumber],
    }));
  };

  const expandAll = () => {
    const all: Record<number, boolean> = {};
    for (let i = 1; i <= 13; i++) all[i] = true;
    setExpandedSteps(all);
  };

  const collapseAll = () => {
    setExpandedSteps({});
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-4xl w-full max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-scaleIn">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-2xl">
              <CloudSun className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">
                  FAO-56 Penman-Monteith Thermodynamic Engine
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  Allen et al. (1998)
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Analytical Reference (ET&#8320;) &amp; Crop Evapotranspiration (ETc = ET&#8320; &times; Kc) Derivation Trace
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Controls */}
        <div className="px-5 pt-3 pb-2 border-b border-slate-800 flex items-center justify-between bg-slate-900/90 text-xs">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl font-semibold transition ${
                activeTab === 'overview'
                  ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300 shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Thermodynamic Balance</span>
            </button>
            <button
              onClick={() => setActiveTab('steps')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl font-semibold transition ${
                activeTab === 'steps'
                  ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300 shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>13-Step Equation Trace</span>
            </button>
            <button
              onClick={() => setActiveTab('simulator')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl font-semibold transition ${
                activeTab === 'simulator'
                  ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300 shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Climate Simulator</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-slate-400">
            <span>Crop:</span>
            <select
              value={selectedCrop}
              onChange={(e) => setSelectedCrop(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 text-xs"
            >
              <option value="Wheat">Wheat</option>
              <option value="Rice">Rice</option>
              <option value="Maize">Maize</option>
              <option value="Cotton">Cotton</option>
              <option value="Sugarcane">Sugarcane</option>
              <option value="Tomato">Tomato</option>
              <option value="Potato">Potato</option>
              <option value="Soybean">Soybean</option>
            </select>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {error && (
            <div className="p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-slate-400">
              <div className="w-8 h-8 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs">Computing FAO-56 thermodynamic energy balance...</span>
            </div>
          ) : derivation ? (
            <>
              {/* TAB 1: OVERVIEW & THERMODYNAMIC BALANCE */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Top Key Readouts */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* ET0 Reference Card */}
                    <div className="bg-slate-950/70 border border-slate-800 p-5 rounded-2xl space-y-2 relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl" />
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">Grass Reference Evapotranspiration (ET&#8320;)</span>
                        <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
                          Standard Grass Canopy
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-extrabold text-amber-300 font-mono">
                          {derivation.et0_mm}
                        </span>
                        <span className="text-sm text-slate-400 font-medium">mm/day</span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Daily atmospheric evaporative demand from hypothetical well-watered grass surface (height 0.12 m, albedo 0.23).
                      </p>
                    </div>

                    {/* ETc Crop Card */}
                    <div className="bg-slate-950/70 border border-emerald-500/30 p-5 rounded-2xl space-y-2 relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl" />
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">
                          Crop Evapotranspiration (ETc = ET&#8320; &times; Kc)
                        </span>
                        <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded capitalize">
                          {selectedCrop} &bull; {growthStage} stage
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-extrabold text-emerald-300 font-mono">
                          {derivation.crop_etc?.etc_mm ?? derivation.et0_mm}
                        </span>
                        <span className="text-sm text-slate-400 font-medium">mm/day</span>
                        <span className="text-xs text-slate-500 ml-2">
                          (Kc = {derivation.crop_etc?.kc ?? 1.0})
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-1.5">
                        <span>Crop Daily Water Requirement:</span>
                        <span className="font-bold text-emerald-400 font-mono">
                          {derivation.crop_etc?.daily_water_liters_per_ha.toLocaleString() ?? '42,000'} L/ha/day
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Growth Stage Selector */}
                  <div className="p-4 bg-slate-950 rounded-2xl border border-slate-800 space-y-2">
                    <span className="text-xs font-semibold text-slate-300 block">
                      Crop Phenological Stage (Kc Factor):
                    </span>
                    <div className="grid grid-cols-4 gap-2">
                      {(['initial', 'development', 'mid', 'late'] as const).map((stage) => (
                        <button
                          key={stage}
                          onClick={() => setGrowthStage(stage)}
                          className={`py-2 px-3 rounded-xl text-xs font-bold capitalize transition border ${
                            growthStage === stage
                              ? 'bg-emerald-600 border-emerald-500 text-white shadow'
                              : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {stage} Stage
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Energy Partitioning Bar (Radiation vs Aerodynamic) */}
                  <div className="p-5 bg-slate-950 rounded-2xl border border-slate-800 space-y-3">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-bold text-slate-200">
                        Energy Balance Partitioning (Radiation vs. Aerodynamic Term)
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Denominator D = &#916; + &#947;(1 + 0.34 u&#8322;)
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="h-4 w-full bg-slate-900 rounded-full overflow-hidden flex border border-slate-800">
                      <div
                        style={{ width: `${derivation.radiation_share_pct}%` }}
                        className="bg-amber-500 h-full transition-all duration-500"
                        title={`Radiation: ${derivation.radiation_share_pct}%`}
                      />
                      <div
                        style={{ width: `${derivation.aerodynamic_share_pct}%` }}
                        className="bg-sky-500 h-full transition-all duration-500"
                        title={`Aerodynamic: ${derivation.aerodynamic_share_pct}%`}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-xs pt-1">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
                        <div>
                          <span className="text-slate-400 block text-[11px]">Radiation Component:</span>
                          <span className="font-bold text-amber-300">
                            {derivation.radiation_term_mm} mm ({derivation.radiation_share_pct}%)
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-sky-500 inline-block" />
                        <div>
                          <span className="text-slate-400 block text-[11px]">Aerodynamic Component:</span>
                          <span className="font-bold text-sky-300">
                            {derivation.aerodynamic_term_mm} mm ({derivation.aerodynamic_share_pct}%)
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Physical Variables Grid */}
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-slate-300 block">
                      Thermodynamic &amp; Atmospheric Variables:
                    </span>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 block uppercase">Net Radiation (Rn)</span>
                        <span className="text-sm font-bold text-slate-200">{derivation.rn_mj_m2} MJ/m&#178;/d</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 block uppercase">Vapour Deficit (VPD)</span>
                        <span className="text-sm font-bold text-sky-300">{derivation.vpd_kpa} kPa</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 block uppercase">Wind Speed (u&#8322;)</span>
                        <span className="text-sm font-bold text-slate-200">{derivation.wind_speed_m_s} m/s</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 block uppercase">Psychrometric (&#947;)</span>
                        <span className="text-sm font-bold text-slate-200">{derivation.gamma_kpa_c} kPa/&#176;C</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: 13-STEP EQUATION TRACE */}
              {activeTab === 'steps' && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-xs pb-1">
                    <span className="text-slate-400">
                      Step-by-step mathematical derivation of FAO-56 Penman-Monteith (Eq. 6):
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={expandAll}
                        className="text-amber-400 hover:text-amber-300 text-[11px] underline"
                      >
                        Expand All
                      </button>
                      <span className="text-slate-600">&bull;</span>
                      <button
                        onClick={collapseAll}
                        className="text-slate-400 hover:text-slate-200 text-[11px] underline"
                      >
                        Collapse All
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    {derivation.steps.map((st) => (
                      <div
                        key={st.step_number}
                        className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden transition"
                      >
                        <button
                          type="button"
                          onClick={() => toggleStep(st.step_number)}
                          className="w-full p-3.5 flex items-center justify-between text-left hover:bg-slate-900/60 transition"
                        >
                          <div className="flex items-center gap-3">
                            <span className="w-6 h-6 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center">
                              {st.step_number}
                            </span>
                            <div>
                              <span className="text-xs font-bold text-slate-200 block">{st.title}</span>
                              <span className="text-[10px] text-slate-500 font-mono">{st.fao_equation}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-xs font-mono font-bold text-amber-300">
                              {st.result_value} {st.result_unit}
                            </span>
                            {expandedSteps[st.step_number] ? (
                              <ChevronUp className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            )}
                          </div>
                        </button>

                        {expandedSteps[st.step_number] && (
                          <div className="p-4 bg-slate-900/40 border-t border-slate-800/80 text-xs space-y-2">
                            <div className="p-2.5 bg-slate-950 rounded-xl border border-slate-800 font-mono text-[11px] text-slate-300">
                              Formula: {st.formula_latex}
                            </div>
                            <p className="text-[11px] text-slate-400">{st.scientific_note}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 3: CLIMATE SIMULATOR */}
              {activeTab === 'simulator' && (
                <div className="space-y-5">
                  <div className="p-4 bg-slate-950 rounded-2xl border border-slate-800 space-y-1">
                    <span className="text-xs font-bold text-slate-200 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      Dynamic Meteorological Sensitivity Analysis
                    </span>
                    <p className="text-[11px] text-slate-400">
                      Adjust input weather variables to evaluate how microclimate shifts alter reference (ET&#8320;) and crop water consumption (ETc).
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Max Temperature */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Max Air Temp (T&#8320;&#8342;&#8339;):</span>
                        <span className="font-bold text-slate-200">{simTempMax} &#176;C</span>
                      </div>
                      <input
                        type="range"
                        min="15"
                        max="50"
                        step="0.5"
                        value={simTempMax}
                        onChange={(e) => setSimTempMax(Number(e.target.value))}
                        className="w-full accent-amber-500"
                      />
                    </div>

                    {/* Min Temperature */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Min Air Temp (T&#8320;&#8326;&#8345;):</span>
                        <span className="font-bold text-slate-200">{simTempMin} &#176;C</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="35"
                        step="0.5"
                        value={simTempMin}
                        onChange={(e) => setSimTempMin(Number(e.target.value))}
                        className="w-full accent-amber-500"
                      />
                    </div>

                    {/* Wind Speed */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Wind Speed at 2m (u&#8322;):</span>
                        <span className="font-bold text-sky-300">{simWindSpeed} m/s</span>
                      </div>
                      <input
                        type="range"
                        min="0.5"
                        max="10.0"
                        step="0.1"
                        value={simWindSpeed}
                        onChange={(e) => setSimWindSpeed(Number(e.target.value))}
                        className="w-full accent-sky-500"
                      />
                    </div>

                    {/* Solar Radiation */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Solar Radiation (Rs):</span>
                        <span className="font-bold text-amber-300">{simSolarRad} MJ/m&#178;/day</span>
                      </div>
                      <input
                        type="range"
                        min="5.0"
                        max="35.0"
                        step="0.5"
                        value={simSolarRad}
                        onChange={(e) => setSimSolarRad(Number(e.target.value))}
                        className="w-full accent-amber-500"
                      />
                    </div>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={handleRunSimulator}
                      disabled={simulating}
                      className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold py-2.5 px-6 rounded-xl text-xs shadow-lg transition disabled:opacity-50"
                    >
                      <Calculator className="w-4 h-4" />
                      <span>{simulating ? 'Calculating...' : 'Recalculate Thermodynamic ET\u2080'}</span>
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-between bg-slate-950/70 text-xs text-slate-400">
          <span>
            Equation Standard: <strong>FAO Irrigation and Drainage Paper No. 56</strong>
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition"
          >
            Close Panel
          </button>
        </div>
      </div>
    </div>
  );
};
