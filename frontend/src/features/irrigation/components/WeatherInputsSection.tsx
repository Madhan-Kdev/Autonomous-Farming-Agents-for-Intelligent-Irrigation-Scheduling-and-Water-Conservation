import React from 'react';
import { CloudSun, Thermometer, Droplets, Wind, CloudRain } from 'lucide-react';

interface Props {
  temperature: number;
  onTemperatureChange: (val: number) => void;
  humidity: number;
  onHumidityChange: (val: number) => void;
  windSpeed: number;
  onWindSpeedChange: (val: number) => void;
  rainfall: number;
  onRainfallChange: (val: number) => void;
  rainProbability: number;
  onRainProbabilityChange: (val: number) => void;
  forecastRainfall: number;
  onForecastRainfallChange: (val: number) => void;
}

export const WeatherInputsSection: React.FC<Props> = ({
  temperature,
  onTemperatureChange,
  humidity,
  onHumidityChange,
  windSpeed,
  onWindSpeedChange,
  rainfall,
  onRainfallChange,
  rainProbability,
  onRainProbabilityChange,
  forecastRainfall,
  onForecastRainfallChange,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-500/10 text-blue-400 rounded-lg">
            <CloudSun className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Atmospheric & Meteorological Conditions</h3>
            <p className="text-xs text-slate-400">
              Climatic drivers for FAO-56 Penman-Monteith ET0 and rainfall postponement rules.
            </p>
          </div>
        </div>
        <span className="text-[10px] font-mono tracking-wide px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/80 text-blue-300">
          SIMULATED / VIRTUAL DATA
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Temperature */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <Thermometer className="w-3.5 h-3.5 text-rose-400" />
              Air Temp
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{temperature.toFixed(1)}°C</span>
          </div>
          <input
            type="number"
            min="-10"
            max="55"
            step="0.5"
            value={temperature}
            onChange={(e) => onTemperatureChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            {temperature < 3 ? '❄️ Frost Alert' : temperature > 38 ? '🔥 Heat Stress' : 'Normal Range'}
          </div>
        </div>

        {/* Humidity */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <Droplets className="w-3.5 h-3.5 text-sky-400" />
              Humidity
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{humidity.toFixed(0)}%</span>
          </div>
          <input
            type="number"
            min="5"
            max="100"
            step="1"
            value={humidity}
            onChange={(e) => onHumidityChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            {humidity < 25 ? 'Dry Vapour Deficit' : humidity > 85 ? 'High Humidity' : 'Optimal'}
          </div>
        </div>

        {/* Wind Speed */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <Wind className="w-3.5 h-3.5 text-teal-400" />
              Wind Speed
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{windSpeed.toFixed(1)} m/s</span>
          </div>
          <input
            type="number"
            min="0"
            max="35"
            step="0.1"
            value={windSpeed}
            onChange={(e) => onWindSpeedChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            {windSpeed > 8.0 ? '💨 Drift Alert (>8m/s)' : 'Good Efficiency'}
          </div>
        </div>

        {/* Current Observed Rain */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <CloudRain className="w-3.5 h-3.5 text-blue-400" />
              Past Rain
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{rainfall.toFixed(1)} mm</span>
          </div>
          <input
            type="number"
            min="0"
            max="150"
            step="0.5"
            value={rainfall}
            onChange={(e) => onRainfallChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            Past 24h accumulated
          </div>
        </div>

        {/* Rain Probability */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <CloudRain className="w-3.5 h-3.5 text-indigo-400" />
              Rain Chance
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{rainProbability.toFixed(0)}%</span>
          </div>
          <input
            type="number"
            min="0"
            max="100"
            step="5"
            value={rainProbability}
            onChange={(e) => onRainProbabilityChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            {rainProbability >= 70 ? '⚠️ High rain likely' : 'Precipitation low'}
          </div>
        </div>

        {/* Forecast Rainfall */}
        <div className="bg-slate-800/60 border border-slate-800 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <CloudRain className="w-3.5 h-3.5 text-cyan-400" />
              Forecast Rain
            </span>
            <span className="font-mono text-xs font-bold text-slate-200">{forecastRainfall.toFixed(1)} mm</span>
          </div>
          <input
            type="number"
            min="0"
            max="200"
            step="0.5"
            value={forecastRainfall}
            onChange={(e) => onForecastRainfallChange(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="mt-1 text-[10px] text-slate-400">
            {forecastRainfall >= 10 ? '🌧️ Triggers postponement' : 'Negligible rain'}
          </div>
        </div>
      </div>
    </div>
  );
};
