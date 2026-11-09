import { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  Droplets, 
  CloudSun, 
  CheckCircle2, 
  Clock, 
  Play, 
  Calendar,
  Layers,
  Sparkles,
  Sliders,
  RotateCcw,
  Flame,
  CloudRain,
  Wind,
  Snowflake,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import type { Farm, AgentState } from './types';
import { IrrigationDecisionPage } from './features/irrigation/IrrigationDecisionPage';

export default function App() {
  const [activeView, setActiveView] = useState<'overview' | 'decision'>('decision');
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [state, setState] = useState<AgentState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [advancing, setAdvancing] = useState<boolean>(false);
  const [msg, setMsg] = useState<string>('');

  useEffect(() => {
    if (window.location.pathname.includes('/irrigation/decision')) {
      setActiveView('decision');
    }
    const handlePopState = () => {
      if (window.location.pathname.includes('/irrigation/decision')) {
        setActiveView('decision');
      } else {
        setActiveView('overview');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigateTo = (view: 'overview' | 'decision') => {
    setActiveView(view);
    const targetPath = view === 'decision' ? '/irrigation/decision' : '/';
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
  };

  // Scenario simulation sandbox state
  const [sandboxOpen, setSandboxOpen] = useState<boolean>(true);
  const [soilMoisture, setSoilMoisture] = useState<number>(18.0);
  const [temperature, setTemperature] = useState<number>(28.0);
  const [rainfall, setRainfall] = useState<number>(0.0);
  const [windSpeed, setWindSpeed] = useState<number>(2.5);
  const [humidity, setHumidity] = useState<number>(55.0);
  const [cropType, setCropType] = useState<string>('Wheat');

  useEffect(() => {
    fetchFarms();
  }, []);

  const fetchFarms = async () => {
    try {
      const res = await axios.get('/api/v1/farms');
      if (res.data.success && res.data.data.length > 0) {
        setFarms(res.data.data);
        setSelectedFarmId(res.data.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch farms:', err);
    }
  };

  const handleRunWorkflow = async (overrideParams?: any) => {
    if (!selectedFarmId) return;
    setLoading(true);
    setMsg('Master Orchestrator triggering 10 specialized domain agents...');
    try {
      const payload: any = {
        farm_id: selectedFarmId,
        user_notes: 'Triggered from web console'
      };
      if (overrideParams) {
        Object.assign(payload, overrideParams);
      }
      const res = await axios.post('/api/v1/agents/run', payload);
      if (res.data.success) {
        setState(res.data.data);
        setMsg('Orchestration workflow completed successfully!');
      }
    } catch (err: any) {
      setMsg(`Workflow failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyScenario = (params: {
    soil?: number;
    temp?: number;
    rain?: number;
    wind?: number;
    humid?: number;
    crop?: string;
  }) => {
    const s = params.soil !== undefined ? params.soil : soilMoisture;
    const t = params.temp !== undefined ? params.temp : temperature;
    const r = params.rain !== undefined ? params.rain : rainfall;
    const w = params.wind !== undefined ? params.wind : windSpeed;
    const h = params.humid !== undefined ? params.humid : humidity;
    const c = params.crop !== undefined ? params.crop : cropType;

    if (params.soil !== undefined) setSoilMoisture(s);
    if (params.temp !== undefined) setTemperature(t);
    if (params.rain !== undefined) setRainfall(r);
    if (params.wind !== undefined) setWindSpeed(w);
    if (params.humid !== undefined) setHumidity(h);
    if (params.crop !== undefined) setCropType(c);

    handleRunWorkflow({
      override_soil_moisture_pct: s,
      override_temperature_c: t,
      override_rainfall_mm: r,
      override_wind_speed_ms: w,
      override_humidity_pct: h,
      crop_type: c,
    });
  };

  const handleAdvanceSimulation = async () => {
    if (!selectedFarmId) return;
    setAdvancing(true);
    setMsg('Advancing virtual farm environmental cycles and IoT telemetry...');
    try {
      const res = await axios.post('/api/v1/simulation/advance', {
        farm_id: selectedFarmId
      });
      if (res.data.success) {
        setMsg(`Virtual simulation stepped to ${res.data.data.target_date}`);
        // Re-run workflow automatically to reflect new daily telemetry
        handleRunWorkflow();
      }
    } catch (err: any) {
      setMsg(`Simulation step failed: ${err.message}`);
      setAdvancing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      {/* Header */}
      <header className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
              <Droplets className="w-8 h-8 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 via-teal-300 to-sky-400 bg-clip-text text-transparent">
                Autonomous Farming Agents
              </h1>
              <p className="text-sm text-slate-400">
                Intelligent Multi-Agent Irrigation Scheduling & Water Conservation
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls for Overview */}
        {activeView === 'overview' && (
          <div className="flex flex-wrap items-center gap-3">
            <select 
              value={selectedFarmId || ''} 
              onChange={(e) => setSelectedFarmId(Number(e.target.value))}
              className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              {farms.map(f => (
                <option key={f.id} value={f.id}>{f.name} ({f.total_area_ha} ha)</option>
              ))}
            </select>

            <button
              onClick={handleAdvanceSimulation}
              disabled={advancing || loading}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
            >
              <Calendar className="w-4 h-4 text-sky-400" />
              {advancing ? 'Stepping...' : 'Step Virtual Day'}
            </button>

            <button
              onClick={handleRunWorkflow}
              disabled={loading}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 rounded-lg text-sm font-semibold shadow-lg shadow-emerald-950 transition disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-white" />
              {loading ? 'Orchestrating...' : 'Run Agents Workflow'}
            </button>
          </div>
        )}
      </header>

      {/* Primary Navigation Tabs */}
      <div className="max-w-7xl mx-auto mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigateTo('decision')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeView === 'decision'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-950 ring-1 ring-emerald-400/40'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            <Sliders className="w-4 h-4 text-emerald-300" />
            <span>Irrigation Decision Console</span>
            <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-300">
              Live AI
            </span>
          </button>

          <button
            type="button"
            onClick={() => navigateTo('overview')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeView === 'overview'
                ? 'bg-slate-800 text-slate-100 shadow-md ring-1 ring-slate-700'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            <Layers className="w-4 h-4 text-sky-400" />
            <span>Overview Dashboard</span>
          </button>
        </div>

        <div className="text-[11px] text-slate-400 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>FastAPI Backend Active (Port 8080)</span>
        </div>
      </div>

      {activeView === 'decision' ? (
        <div className="max-w-7xl mx-auto">
          <IrrigationDecisionPage />
        </div>
      ) : (
        /* Main Grid */
        <main className="max-w-7xl mx-auto space-y-6">
        {msg && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 text-sm flex items-center justify-between text-slate-300">
            <span>{msg}</span>
            {loading && <span className="animate-spin text-emerald-400">⏳</span>}
          </div>
        )}

        {/* Interactive What-If Scenario Sandbox */}
        <section className="bg-slate-900/70 border border-emerald-500/30 rounded-2xl p-5 shadow-xl shadow-slate-950/50 backdrop-blur">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setSandboxOpen(!sandboxOpen)}>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30">
                <Sliders className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">Interactive What-If Simulation Sandbox</h2>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    Live Testing
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Change inputs (moisture, temperature, rain, wind, crop) and see the multi-agent decision adapt in real-time.
                </p>
              </div>
            </div>
            <button className="text-slate-400 hover:text-white p-1">
              {sandboxOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          </div>

          {sandboxOpen && (
            <div className="mt-5 space-y-5 pt-4 border-t border-slate-800/80">
              {/* Preset Scenario Buttons */}
              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                  ⚡ 1-Click Preset Scenarios:
                </span>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleApplyScenario({ soil: 9.0, temp: 38.0, rain: 0.0, wind: 3.0, humid: 30.0 })}
                    className="flex items-center gap-1.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <Flame className="w-3.5 h-3.5" /> Severe Drought (9% Soil, 38°C)
                  </button>
                  <button
                    onClick={() => handleApplyScenario({ rain: 25.0, soil: 24.0, temp: 22.0, wind: 4.0, humid: 85.0 })}
                    className="flex items-center gap-1.5 text-xs bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <CloudRain className="w-3.5 h-3.5" /> Heavy Rain (25mm Forecast)
                  </button>
                  <button
                    onClick={() => handleApplyScenario({ wind: 9.5, soil: 18.0, rain: 0.0, temp: 24.0 })}
                    className="flex items-center gap-1.5 text-xs bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <Wind className="w-3.5 h-3.5" /> High Wind Gale (9.5 m/s)
                  </button>
                  <button
                    onClick={() => handleApplyScenario({ soil: 33.0, rain: 0.0, temp: 24.0, wind: 2.0 })}
                    className="flex items-center gap-1.5 text-xs bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <Droplets className="w-3.5 h-3.5" /> Saturated Soil (33%)
                  </button>
                  <button
                    onClick={() => handleApplyScenario({ temp: 0.5, wind: 1.5, rain: 0.0, soil: 19.0 })}
                    className="flex items-center gap-1.5 text-xs bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <Snowflake className="w-3.5 h-3.5" /> Frost Hazard (0.5°C)
                  </button>
                  <button
                    onClick={() => handleApplyScenario({ soil: 26.0, temp: 25.0, rain: 0.0, wind: 2.0 })}
                    className="flex items-center gap-1.5 text-xs bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-lg font-medium transition"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" /> Optimal Moisture (26%)
                  </button>
                </div>
              </div>

              {/* Sliders & Parameters Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                {/* Soil Moisture */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">🌱 Soil Moisture</span>
                    <span className="text-emerald-400 font-bold">{soilMoisture.toFixed(1)}%</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="40"
                    step="0.5"
                    value={soilMoisture}
                    onChange={(e) => setSoilMoisture(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>5% (Wilting)</span>
                    <span>20% (Normal)</span>
                    <span>40% (Saturated)</span>
                  </div>
                </div>

                {/* Temperature */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">🌡️ Temperature</span>
                    <span className="text-amber-400 font-bold">{temperature.toFixed(1)}°C</span>
                  </div>
                  <input
                    type="range"
                    min="-5"
                    max="45"
                    step="0.5"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>-5°C (Frost)</span>
                    <span>25°C (Mild)</span>
                    <span>45°C (Extreme)</span>
                  </div>
                </div>

                {/* Rainfall */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">🌧️ Rainfall Forecast</span>
                    <span className="text-sky-400 font-bold">{rainfall.toFixed(1)} mm</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="50"
                    step="1"
                    value={rainfall}
                    onChange={(e) => setRainfall(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>0 mm (Dry)</span>
                    <span>10 mm (Threshold)</span>
                    <span>50 mm (Heavy)</span>
                  </div>
                </div>

                {/* Wind Speed */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">💨 Wind Speed</span>
                    <span className="text-cyan-400 font-bold">{windSpeed.toFixed(1)} m/s</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="15"
                    step="0.5"
                    value={windSpeed}
                    onChange={(e) => setWindSpeed(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>0 m/s (Calm)</span>
                    <span>5 m/s (Elevated)</span>
                    <span>15 m/s (Gale)</span>
                  </div>
                </div>

                {/* Humidity */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">💧 Air Humidity</span>
                    <span className="text-indigo-400 font-bold">{humidity.toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    step="5"
                    value={humidity}
                    onChange={(e) => setHumidity(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-400"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>10% (Arid)</span>
                    <span>50% (Average)</span>
                    <span>100% (Humid)</span>
                  </div>
                </div>

                {/* Crop Selection */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-300 font-medium">🌾 Crop Profile</span>
                    <span className="text-emerald-300 font-semibold">{cropType}</span>
                  </div>
                  <select
                    value={cropType}
                    onChange={(e) => setCropType(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-400"
                  >
                    {['Wheat', 'Maize', 'Tomato', 'Cotton', 'Rice', 'Sugarcane', 'Potato', 'Barley', 'Soybean', 'Sorghum'].map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-slate-500">Applies FAO-56 crop coefficients & root depth</p>
                </div>
              </div>

              {/* Sandbox Action Trigger Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleApplyScenario({
                      soil: soilMoisture,
                      temp: temperature,
                      rain: rainfall,
                      wind: windSpeed,
                      humid: humidity,
                      crop: cropType,
                    })}
                    disabled={loading}
                    className="flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold px-5 py-2 rounded-xl text-sm shadow-lg shadow-emerald-950/40 transition disabled:opacity-50 cursor-pointer"
                  >
                    <Sparkles className="w-4 h-4 text-slate-950 fill-slate-950" />
                    {loading ? 'Simulating...' : 'Run Scenario with Custom Inputs'}
                  </button>
                  <button
                    onClick={() => {
                      setSoilMoisture(18.0);
                      setTemperature(28.0);
                      setRainfall(0.0);
                      setWindSpeed(2.5);
                      setHumidity(55.0);
                      setCropType('Wheat');
                      handleRunWorkflow();
                    }}
                    disabled={loading}
                    className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl text-sm font-medium transition cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Reset to Farm Baseline
                  </button>
                </div>
                <span className="text-[11px] text-slate-500">
                  ⚡ All calculations strictly follow FAO-56 Penman-Monteith physics & ML models.
                </span>
              </div>
            </div>
          )}
        </section>

        {state ? (
          <>
            {/* Top Stat Row: Primary Decision & Water Conservation */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Decision Panel */}
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur flex flex-col justify-between">
                <div>
                  <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Irrigation Directive</span>
                  <div className="mt-2 flex items-center gap-3">
                    <span className={`text-2xl font-black px-3 py-1 rounded-md ${
                      state.irrigation_decision.decision === 'REQUIRED' 
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                        : state.irrigation_decision.decision === 'POSTPONED'
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        : 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                    }`}>
                      {state.irrigation_decision.decision}
                    </span>
                    <span className="text-xs text-slate-400 font-medium px-2 py-1 bg-slate-800 rounded">
                      Priority: {state.irrigation_decision.priority}
                    </span>
                  </div>
                  <p className="mt-4 text-sm text-slate-300">
                    {state.advisory.recommended_action}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
                  <span>Confidence: {(state.advisory.confidence * 100).toFixed(0)}%</span>
                  <span>Rec Depth: {state.irrigation_decision.recommended_volume_mm?.toFixed(1) || 0} mm</span>
                </div>
              </div>

              {/* Water Optimization Panel */}
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur flex flex-col justify-between">
                <div>
                  <span className="text-xs uppercase tracking-wider text-emerald-400 font-semibold">Water Conservation</span>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-4xl font-extrabold text-white">
                      {state.optimization.water_saving_pct?.toFixed(1) || '0.0'}%
                    </span>
                    <span className="text-sm text-slate-400">Conserved</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    Saved <strong className="text-emerald-400">{state.optimization.water_saving_mm?.toFixed(1) || 0} mm</strong> compared to standard {state.optimization.baseline_volume_mm?.toFixed(1)} mm schedule.
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
                  <span>Over-irrigation averted:</span>
                  <span className={state.optimization.over_irrigation_detected ? 'text-emerald-400' : 'text-slate-400'}>
                    {state.optimization.over_irrigation_detected ? 'Yes (Deep drainage prevented)' : 'None detected'}
                  </span>
                </div>
              </div>

              {/* Risk & Safety Panel */}
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 backdrop-blur flex flex-col justify-between">
                <div>
                  <span className="text-xs uppercase tracking-wider text-amber-400 font-semibold">Risk & Hazard Audit</span>
                  <div className="mt-2 flex items-center gap-2">
                    <span className={`text-xl font-bold ${
                      state.risk.overall_risk_level === 'CRITICAL' ? 'text-red-400' :
                      state.risk.overall_risk_level === 'HIGH' ? 'text-amber-400' :
                      'text-slate-200'
                    }`}>
                      Level: {state.risk.overall_risk_level}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    {state.risk.risk_summary || 'All environmental and hydraulic indicators nominal.'}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
                  <span>Recommendation Safe:</span>
                  <span className={state.risk.recommendation_safe ? 'text-emerald-400' : 'text-red-400'}>
                    {state.risk.recommendation_safe ? 'Safe to execute' : 'Action restricted'}
                  </span>
                </div>
              </div>
            </div>

            {/* Zone Irrigation Visualizer & Soil Status */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Zone Plans List */}
              <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-semibold flex items-center gap-2 text-slate-200">
                    <Layers className="w-4 h-4 text-emerald-400" />
                    Multi-Zone Precision Irrigation Plans
                  </h3>
                  <span className="text-xs text-slate-400">{state.zone_plans.length} active zones</span>
                </div>

                <div className="space-y-3">
                  {state.zone_plans.map((zp) => (
                    <div key={zp.zone_id} className="bg-slate-950/70 border border-slate-800/60 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-100">{zp.zone_name}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            zp.irrigation_required ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'
                          }`}>
                            {zp.irrigation_required ? 'Irrigate' : 'Idle'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Moisture Stress Index: <strong className="text-slate-200">{(zp.stress_index * 100).toFixed(0)}%</strong>
                        </p>
                      </div>

                      <div className="flex items-center gap-6 text-sm">
                        <div className="text-right">
                          <span className="text-xs text-slate-400 block">Scheduled Volume</span>
                          <span className="font-mono text-emerald-400 font-bold">{zp.recommended_volume_mm.toFixed(1)} mm</span>
                        </div>
                        <div className="text-right">
                          <span className="text-xs text-slate-400 block">Priority</span>
                          <span className="text-xs font-semibold px-2 py-0.5 bg-slate-800 rounded text-slate-300">{zp.priority}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Weather & ET0 Summary Card */}
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-between">
                <div>
                  <h3 className="text-base font-semibold flex items-center gap-2 text-slate-200 mb-4">
                    <CloudSun className="w-4 h-4 text-sky-400" />
                    Agro-Meteorology & ET₀
                  </h3>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Temperature</span>
                      <span className="font-semibold">{state.weather.temperature_c?.toFixed(1)}°C</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Relative Humidity</span>
                      <span className="font-semibold">{state.weather.humidity_pct?.toFixed(0)}%</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Wind Velocity</span>
                      <span className="font-semibold">{state.weather.wind_speed_ms?.toFixed(1)} m/s</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">FAO-56 Reference ET₀</span>
                      <span className="font-semibold text-emerald-400">{state.et0.et0_reference_mm?.toFixed(2)} mm/day</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">ML Forecast ET₀</span>
                      <span className="font-semibold text-teal-400">{state.et0.et0_predicted_mm?.toFixed(2)} mm/day</span>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-slate-400 mt-4 pt-3 border-t border-slate-800/60">
                  {state.weather.weather_summary || 'Weather suitability verified.'}
                </p>
              </div>
            </div>

            {/* Explainable AI Rationale Section */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-5 h-5 text-amber-400" />
                <h3 className="text-lg font-bold text-white">
                  Explainable AI Farmer Advisory & Agronomic Rationale
                </h3>
              </div>
              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                {state.advisory.full_explanation}
              </div>
            </div>

            {/* Agent Execution Timeline Telemetry */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6">
              <h3 className="text-base font-semibold flex items-center gap-2 text-slate-200 mb-4">
                <Clock className="w-4 h-4 text-emerald-400" />
                LangGraph Multi-Agent Execution Telemetry
              </h3>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {state.agent_executions.map((exec, idx) => (
                  <div key={idx} className="bg-slate-950/60 border border-slate-800/60 rounded-lg p-3 text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-slate-300 truncate">{exec.agent_name}</span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    </div>
                    <span className="text-slate-400 font-mono">
                      {exec.duration_ms ? `${exec.duration_ms.toFixed(1)} ms` : 'Complete'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-20 bg-slate-900/40 border border-dashed border-slate-800 rounded-2xl">
            <Droplets className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h2 className="text-lg font-medium text-slate-300">Ready to Orchestrate Farm Intelligence</h2>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-2">
              Select a farm and click <strong className="text-slate-300">"Run Agents Workflow"</strong> to trigger the complete 10-node AI agent pipeline or <strong className="text-slate-300">"Step Virtual Day"</strong> to advance simulation.
            </p>
          </div>
        )}
      </main>
      )}
    </div>
  );
}
