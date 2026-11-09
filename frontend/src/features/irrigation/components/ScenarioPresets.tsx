import React from 'react';
import type { PresetKey, PresetScenario, IrrigationDecisionRequest } from '../types';
import { Sun, Flame, CloudRain, ShieldAlert, Waves, Wind, Snowflake, Droplet } from 'lucide-react';

interface Props {
  onSelectPreset: (presetValues: Partial<IrrigationDecisionRequest>) => void;
  activePreset: PresetKey | 'custom';
}

export const PRESETS: PresetScenario[] = [
  {
    id: 'normal',
    label: 'Normal Day',
    badge: 'Baseline',
    description: 'Moderate temperature (24°C), mild moisture (22%), fair weather. Routine check.',
    values: {
      temperature: 24.0,
      humidity: 55.0,
      wind_speed: 2.2,
      rainfall: 0.0,
      rain_probability: 10.0,
      forecast_rainfall: 0.0,
      soil_moisture: 22.0,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Clay Loam',
      growth_stage: 'development',
      water_availability: 'Normal',
      available_water_liters: 150000,
    },
  },
  {
    id: 'dry',
    label: 'Hot & Dry',
    badge: 'High Stress',
    description: 'High heat (36°C), low humidity (22%), soil drying rapidly (15%). High irrigation demand.',
    values: {
      temperature: 36.5,
      humidity: 22.0,
      wind_speed: 4.8,
      rainfall: 0.0,
      rain_probability: 5.0,
      forecast_rainfall: 0.0,
      soil_moisture: 15.0,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Sandy Loam',
      growth_stage: 'mid',
      water_availability: 'Normal',
      available_water_liters: 120000,
    },
  },
  {
    id: 'rainy',
    label: 'Rain Expected',
    badge: 'Postponement',
    description: 'Incoming storm (85% rain chance, 28mm forecast). Irrigation postponed to save water.',
    values: {
      temperature: 19.5,
      humidity: 88.0,
      wind_speed: 6.2,
      rainfall: 5.0,
      rain_probability: 85.0,
      forecast_rainfall: 28.0,
      soil_moisture: 26.0,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Loam',
      growth_stage: 'mid',
      water_availability: 'Normal',
      available_water_liters: 150000,
    },
  },
  {
    id: 'drought',
    label: 'Severe Drought',
    badge: 'Deficit Mode',
    description: 'Extreme heat (41°C), desiccated soil (11% below WP), scarce reservoir. Emergency deficit allocation.',
    values: {
      temperature: 41.0,
      humidity: 15.0,
      wind_speed: 5.5,
      rainfall: 0.0,
      rain_probability: 0.0,
      forecast_rainfall: 0.0,
      soil_moisture: 11.0,
      field_capacity: 30.0,
      wilting_point: 13.0,
      soil_type: 'Sandy Loam',
      growth_stage: 'mid',
      water_availability: 'Critical',
      available_water_liters: 15000,
    },
  },
  {
    id: 'saturated',
    label: 'Saturated Soil',
    badge: 'Over-wet',
    description: 'Recent deluge (soil moisture 38% > Field Capacity). Irrigation suppressed to prevent waterlogging & root rot.',
    values: {
      temperature: 21.0,
      humidity: 92.0,
      wind_speed: 1.8,
      rainfall: 35.0,
      rain_probability: 40.0,
      forecast_rainfall: 2.0,
      soil_moisture: 38.0,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Clay Loam',
      growth_stage: 'development',
      water_availability: 'Normal',
      available_water_liters: 200000,
    },
  },
  {
    id: 'high_wind',
    label: 'High Wind Event',
    badge: 'Drift Risk',
    description: 'Gale conditions (12.5 m/s). Risk agent flags high droplet evaporation & spray drift.',
    values: {
      temperature: 28.0,
      humidity: 40.0,
      wind_speed: 12.5,
      rainfall: 0.0,
      rain_probability: 10.0,
      forecast_rainfall: 0.0,
      soil_moisture: 18.0,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Sandy Loam',
      growth_stage: 'mid',
      water_availability: 'Normal',
      available_water_liters: 100000,
    },
  },
  {
    id: 'frost',
    label: 'Near-Frost Danger',
    badge: 'Temperature Alert',
    description: 'Sub-zero approach (1.5°C). Freezing ground safety thresholds evaluated.',
    values: {
      temperature: 1.5,
      humidity: 70.0,
      wind_speed: 1.2,
      rainfall: 0.0,
      rain_probability: 5.0,
      forecast_rainfall: 0.0,
      soil_moisture: 20.0,
      field_capacity: 30.0,
      wilting_point: 13.0,
      soil_type: 'Loam',
      growth_stage: 'initial',
      water_availability: 'Normal',
      available_water_liters: 100000,
    },
  },
  {
    id: 'low_water',
    label: 'Depleted Water Supply',
    badge: 'Volume Constraint',
    description: 'Low water reserve (25,000 L). Optimizer scales application depth strictly within water limits.',
    values: {
      temperature: 30.0,
      humidity: 35.0,
      wind_speed: 3.0,
      rainfall: 0.0,
      rain_probability: 0.0,
      forecast_rainfall: 0.0,
      soil_moisture: 16.5,
      field_capacity: 32.0,
      wilting_point: 14.0,
      soil_type: 'Loam',
      growth_stage: 'mid',
      water_availability: 'Low',
      available_water_liters: 25000,
    },
  },
];

const getPresetIcon = (id: PresetKey) => {
  switch (id) {
    case 'normal': return <Sun className="w-4 h-4 text-emerald-500" />;
    case 'dry': return <Flame className="w-4 h-4 text-amber-500" />;
    case 'rainy': return <CloudRain className="w-4 h-4 text-sky-500" />;
    case 'drought': return <ShieldAlert className="w-4 h-4 text-rose-500" />;
    case 'saturated': return <Waves className="w-4 h-4 text-blue-500" />;
    case 'high_wind': return <Wind className="w-4 h-4 text-teal-500" />;
    case 'frost': return <Snowflake className="w-4 h-4 text-cyan-400" />;
    case 'low_water': return <Droplet className="w-4 h-4 text-orange-500" />;
  }
};

export const ScenarioPresets: React.FC<Props> = ({ onSelectPreset, activePreset }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg">
            <Sun className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Agricultural Scenario Presets</h3>
            <p className="text-xs text-slate-400">
              Load realistic agro-climatic stress profiles with 1 click. You can freely edit any parameter below.
            </p>
          </div>
        </div>
        {activePreset === 'custom' && (
          <span className="text-xs px-2.5 py-1 rounded-full font-mono bg-slate-800 text-slate-300 border border-slate-700">
            Custom Inputs Active
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        {PRESETS.map((p) => {
          const isSelected = activePreset === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelectPreset(p.values)}
              className={`p-2.5 rounded-lg text-left transition-all border flex flex-col justify-between ${
                isSelected
                  ? 'bg-emerald-950/40 border-emerald-500 text-emerald-100 ring-1 ring-emerald-500/50 shadow-sm'
                  : 'bg-slate-800/60 border-slate-700/60 hover:bg-slate-800 hover:border-slate-600 text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5 w-full">
                {getPresetIcon(p.id)}
                <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${
                  isSelected ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-700 text-slate-400'
                }`}>
                  {p.badge}
                </span>
              </div>
              <div>
                <div className="text-xs font-semibold">{p.label}</div>
                <div className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-tight">
                  {p.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
