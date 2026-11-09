import React, { useEffect, useState } from 'react';
import type {
  Farm,
  CropOut,
  DetailedAgentState,
  IrrigationDecisionRequest,
  IrrigationHistoryRecord,
  PresetKey,
} from './types';
import {
  fetchFarms,
  fetchCrops,
  executeIrrigationDecision,
  fetchIrrigationHistory,
} from './api';
import { ScenarioPresets } from './components/ScenarioPresets';
import { FarmContextSection } from './components/FarmContextSection';
import { CropInputsSection } from './components/CropInputsSection';
import { SoilInputsSection } from './components/SoilInputsSection';
import { WeatherInputsSection } from './components/WeatherInputsSection';
import { WaterAvailabilitySection } from './components/WaterAvailabilitySection';
import { ExecutionOptionsSection } from './components/ExecutionOptionsSection';
import { FinalDecisionCard } from './components/FinalDecisionCard';
import { AgriculturalStateCard } from './components/AgriculturalStateCard';
import { AgentExecutionGraph } from './components/AgentExecutionGraph';
import { DecisionEvidenceChain } from './components/DecisionEvidenceChain';
import { DecisionHistoryTable } from './components/DecisionHistoryTable';
import { ScenarioComparisonModal } from './components/ScenarioComparisonModal';
import {
  Sliders,
  GitCompare,
  AlertCircle,
} from 'lucide-react';

export const IrrigationDecisionPage: React.FC = () => {
  // Master data
  const [farms, setFarms] = useState<Farm[]>([]);
  const [crops, setCrops] = useState<CropOut[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<number>(1);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<number | null>(null);

  // Active Preset
  const [activePreset, setActivePreset] = useState<PresetKey | 'custom'>('normal');

  // Agricultural & Hydrological Inputs
  const [cropType, setCropType] = useState<string>('Wheat');
  const [growthStage, setGrowthStage] = useState<'initial' | 'development' | 'mid' | 'late'>('development');
  const [soilMoisture, setSoilMoisture] = useState<number>(22.0);
  const [fieldCapacity, setFieldCapacity] = useState<number>(32.0);
  const [wiltingPoint, setWiltingPoint] = useState<number>(14.0);
  const [soilType, setSoilType] = useState<string>('Clay Loam');

  // Weather & Atmosphere Inputs
  const [temperature, setTemperature] = useState<number>(24.0);
  const [humidity, setHumidity] = useState<number>(55.0);
  const [windSpeed, setWindSpeed] = useState<number>(2.2);
  const [rainfall, setRainfall] = useState<number>(0.0);
  const [rainProbability, setRainProbability] = useState<number>(10.0);
  const [forecastRainfall, setForecastRainfall] = useState<number>(0.0);

  // Water Reserve Inputs
  const [waterAvailability, setWaterAvailability] = useState<'Normal' | 'Limited' | 'Low' | 'Critical'>('Normal');
  const [availableWaterLiters, setAvailableWaterLiters] = useState<number>(150000);

  // Workflow Execution Controls
  const [runFullWorkflow, setRunFullWorkflow] = useState<boolean>(true);
  const [useEt0Prediction, setUseEt0Prediction] = useState<boolean>(true);
  const [useHistoricalData, setUseHistoricalData] = useState<boolean>(true);
  const [userNotes, setUserNotes] = useState<string>('');

  // Results & Telemetry
  const [latestState, setLatestState] = useState<DetailedAgentState | null>(null);
  const [previousState, setPreviousState] = useState<DetailedAgentState | null>(null);
  const [history, setHistory] = useState<IrrigationHistoryRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState<boolean>(false);

  // Initial Load
  useEffect(() => {
    loadMasterData();
  }, []);

  const loadMasterData = async () => {
    try {
      const [farmList, cropList] = await Promise.all([fetchFarms(), fetchCrops()]);
      setFarms(farmList);
      if (farmList.length > 0) {
        setSelectedFarmId(farmList[0].id);
      }
      setCrops(cropList);
      if (cropList.length > 0) {
        setCropType(cropList[0].name);
      }
      loadHistory(farmList[0]?.id);
    } catch (err: any) {
      console.error('Master data fetch error:', err);
    }
  };

  const loadHistory = async (farmId?: number, zoneId?: number) => {
    setIsHistoryLoading(true);
    try {
      const hist = await fetchIrrigationHistory(farmId, zoneId, 25);
      setHistory(hist);
    } catch (err) {
      console.error('History fetch failed:', err);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const handlePresetSelect = (values: Partial<IrrigationDecisionRequest>) => {
    if (typeof values.temperature === 'number') setTemperature(values.temperature);
    if (typeof values.humidity === 'number') setHumidity(values.humidity);
    if (typeof values.wind_speed === 'number') setWindSpeed(values.wind_speed);
    if (typeof values.rainfall === 'number') setRainfall(values.rainfall);
    if (typeof values.rain_probability === 'number') setRainProbability(values.rain_probability);
    if (typeof values.forecast_rainfall === 'number') setForecastRainfall(values.forecast_rainfall);
    if (typeof values.soil_moisture === 'number') setSoilMoisture(values.soil_moisture);
    if (typeof values.field_capacity === 'number') setFieldCapacity(values.field_capacity);
    if (typeof values.wilting_point === 'number') setWiltingPoint(values.wilting_point);
    if (typeof values.soil_type === 'string') setSoilType(values.soil_type);
    if (values.growth_stage) setGrowthStage(values.growth_stage);
    if (values.water_availability) setWaterAvailability(values.water_availability);
    if (typeof values.available_water_liters === 'number') setAvailableWaterLiters(values.available_water_liters);

    // Match by signature values
    if (values.temperature === 36.5) setActivePreset('dry');
    else if (values.rain_probability === 85.0) setActivePreset('rainy');
    else if (values.temperature === 41.0) setActivePreset('drought');
    else if (values.soil_moisture === 38.0) setActivePreset('saturated');
    else if (values.wind_speed === 12.5) setActivePreset('high_wind');
    else if (values.temperature === 1.5) setActivePreset('frost');
    else if (values.water_availability === 'Low') setActivePreset('low_water');
    else setActivePreset('normal');
  };

  const handleRunDecision = async () => {
    if (fieldCapacity <= wiltingPoint) {
      setErrorMsg('Field Capacity must be strictly greater than Wilting Point.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    const payload: IrrigationDecisionRequest = {
      farm_id: selectedFarmId,
      field_id: selectedFieldId,
      zone_id: selectedZoneId,
      crop_type: cropType,
      growth_stage: growthStage,
      soil_moisture: soilMoisture,
      field_capacity: fieldCapacity,
      wilting_point: wiltingPoint,
      soil_type: soilType,
      temperature,
      humidity,
      wind_speed: windSpeed,
      rainfall,
      rain_probability: rainProbability,
      forecast_rainfall: forecastRainfall,
      water_availability: waterAvailability,
      available_water_liters: availableWaterLiters,
      use_historical_data: useHistoricalData,
      use_et0_prediction: useEt0Prediction,
      run_full_workflow: runFullWorkflow,
      user_notes: userNotes || `Scenario: ${activePreset}`,
    };

    try {
      const state = await executeIrrigationDecision(payload);
      if (latestState) {
        setPreviousState(latestState);
      }
      setLatestState(state);
      loadHistory(selectedFarmId, selectedZoneId ?? undefined);

      // Smooth scroll down to results
      setTimeout(() => {
        const el = document.getElementById('decision-results-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 150);
    } catch (err: any) {
      console.error('Decision execution error:', err);
      setErrorMsg(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Agent workflow failed to execute.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-6 px-4 sm:px-6 lg:px-8 space-y-6">
      {/* Top Banner & Title */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] uppercase font-bold tracking-widest px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Interactive Autonomous AI Console
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300">
              SIMULATED / VIRTUAL DATA
            </span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2.5">
            Irrigation Decision & Agent Experimentation Console
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-3xl">
            Input soil, weather, crop, and hydraulic parameters to execute the genuine 10-agent LangGraph orchestration pipeline. All calculations derive from deterministic agronomic physics (FAO-56 Penman-Monteith) and trained ML regressors.
          </p>
        </div>

        {previousState && latestState && (
          <button
            type="button"
            onClick={() => setShowComparison(true)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-emerald-300 transition-colors shadow-sm"
          >
            <GitCompare className="w-4 h-4 text-emerald-400" />
            Compare Run A vs Run B
          </button>
        )}
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="p-4 bg-rose-950/50 border border-rose-600 rounded-xl flex items-start gap-3 text-xs text-rose-200 shadow-md">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-sm text-rose-300">Execution Error</div>
            <div className="mt-0.5">{errorMsg}</div>
          </div>
        </div>
      )}

      {/* 1-Click Agricultural Scenario Presets */}
      <ScenarioPresets
        activePreset={activePreset}
        onSelectPreset={(p) => {
          handlePresetSelect(p);
        }}
      />

      {/* Input Configuration Sections */}
      <div className="space-y-4">
        {/* Spatial / Farm Targeting */}
        <FarmContextSection
          farms={farms}
          selectedFarmId={selectedFarmId}
          onSelectFarm={(fid) => {
            setSelectedFarmId(fid);
            loadHistory(fid);
          }}
          selectedFieldId={selectedFieldId}
          onSelectField={setSelectedFieldId}
          selectedZoneId={selectedZoneId}
          onSelectZone={(zid) => {
            setSelectedZoneId(zid);
            loadHistory(selectedFarmId, zid ?? undefined);
          }}
        />

        {/* Crop Species & Growth Stage */}
        <CropInputsSection
          crops={crops}
          cropType={cropType}
          onCropTypeChange={(val) => {
            setCropType(val);
            setActivePreset('custom');
          }}
          growthStage={growthStage}
          onGrowthStageChange={(val) => {
            setGrowthStage(val);
            setActivePreset('custom');
          }}
        />

        {/* Soil Moisture & Hydrology Matrix */}
        <SoilInputsSection
          soilMoisture={soilMoisture}
          onSoilMoistureChange={(val) => {
            setSoilMoisture(val);
            setActivePreset('custom');
          }}
          fieldCapacity={fieldCapacity}
          onFieldCapacityChange={(val) => {
            setFieldCapacity(val);
            setActivePreset('custom');
          }}
          wiltingPoint={wiltingPoint}
          onWiltingPointChange={(val) => {
            setWiltingPoint(val);
            setActivePreset('custom');
          }}
          soilType={soilType}
          onSoilTypeChange={(val) => {
            setSoilType(val);
            setActivePreset('custom');
          }}
        />

        {/* Weather & Meteorological Drivers */}
        <WeatherInputsSection
          temperature={temperature}
          onTemperatureChange={(val) => {
            setTemperature(val);
            setActivePreset('custom');
          }}
          humidity={humidity}
          onHumidityChange={(val) => {
            setHumidity(val);
            setActivePreset('custom');
          }}
          windSpeed={windSpeed}
          onWindSpeedChange={(val) => {
            setWindSpeed(val);
            setActivePreset('custom');
          }}
          rainfall={rainfall}
          onRainfallChange={(val) => {
            setRainfall(val);
            setActivePreset('custom');
          }}
          rainProbability={rainProbability}
          onRainProbabilityChange={(val) => {
            setRainProbability(val);
            setActivePreset('custom');
          }}
          forecastRainfall={forecastRainfall}
          onForecastRainfallChange={(val) => {
            setForecastRainfall(val);
            setActivePreset('custom');
          }}
        />

        {/* Water Storage Availability */}
        <WaterAvailabilitySection
          waterAvailability={waterAvailability}
          onWaterAvailabilityChange={(val) => {
            setWaterAvailability(val);
            setActivePreset('custom');
          }}
          availableWaterLiters={availableWaterLiters}
          onAvailableWaterLitersChange={(val) => {
            setAvailableWaterLiters(val);
            setActivePreset('custom');
          }}
        />

        {/* Execution Options & Trigger Button */}
        <ExecutionOptionsSection
          runFullWorkflow={runFullWorkflow}
          onRunFullWorkflowChange={setRunFullWorkflow}
          useEt0Prediction={useEt0Prediction}
          onUseEt0PredictionChange={setUseEt0Prediction}
          useHistoricalData={useHistoricalData}
          onUseHistoricalDataChange={setUseHistoricalData}
          userNotes={userNotes}
          onUserNotesChange={setUserNotes}
          onSubmit={handleRunDecision}
          isLoading={isLoading}
          isInvalidBounds={fieldCapacity <= wiltingPoint}
        />
      </div>

      {/* Model Output & Results Section */}
      <div id="decision-results-section" className="space-y-6 pt-4">
        {latestState ? (
          <>
            {/* Final Decision Card */}
            <FinalDecisionCard state={latestState} />

            {/* Agricultural State with Provenance Badges */}
            <AgriculturalStateCard state={latestState} />

            {/* 10-Agent LangGraph Execution Pipeline Graph */}
            <AgentExecutionGraph executions={latestState.agent_executions || []} />

            {/* Physical Causality Chain */}
            <DecisionEvidenceChain state={latestState} />
          </>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto mb-3">
              <Sliders className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-200">
              Interactive Irrigation Decision Ready
            </h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
              Select an agricultural scenario preset above or tune environmental variables, then click{' '}
              <strong className="text-emerald-400">Run Multi-Agent Decision Workflow</strong> to trigger the live backend LangGraph execution.
            </p>
          </div>
        )}

        {/* Persistent Execution History */}
        <DecisionHistoryTable
          history={history}
          isLoading={isHistoryLoading}
        />
      </div>

      {/* Comparison Modal */}
      {showComparison && (
        <ScenarioComparisonModal
          runA={previousState}
          runB={latestState}
          onClose={() => setShowComparison(false)}
        />
      )}
    </div>
  );
};
