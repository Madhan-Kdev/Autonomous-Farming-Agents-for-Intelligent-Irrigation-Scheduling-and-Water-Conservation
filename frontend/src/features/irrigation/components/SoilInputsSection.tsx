import { Layers, AlertTriangle } from 'lucide-react';

interface Props {
  soilMoisture: number;
  onSoilMoistureChange: (val: number) => void;
  fieldCapacity: number;
  onFieldCapacityChange: (val: number) => void;
  wiltingPoint: number;
  onWiltingPointChange: (val: number) => void;
  soilType: string;
  onSoilTypeChange: (val: string) => void;
}

export const SOIL_TYPES = [
  { name: 'Sandy Loam', fc: 18.0, wp: 8.0, desc: 'Coarse texture, high drainage, low AWC' },
  { name: 'Loam', fc: 27.0, wp: 12.0, desc: 'Balanced medium texture, optimal agronomic balance' },
  { name: 'Clay Loam', fc: 32.0, wp: 14.0, desc: 'Fine texture, moderate-high moisture retention' },
  { name: 'Silty Clay', fc: 38.0, wp: 19.0, desc: 'Heavy clay, high water retention, slow infiltration' },
  { name: 'Custom Soil', fc: 30.0, wp: 15.0, desc: 'Manual moisture limits configuration' },
];

export const SoilInputsSection: React.FC<Props> = ({
  soilMoisture,
  onSoilMoistureChange,
  fieldCapacity,
  onFieldCapacityChange,
  wiltingPoint,
  onWiltingPointChange,
  soilType,
  onSoilTypeChange,
}) => {
  const isInvalidBounds = fieldCapacity <= wiltingPoint;
  const awc = Math.max(0, fieldCapacity - wiltingPoint);
  const currentAvailablePct =
    fieldCapacity > wiltingPoint
      ? Math.max(0, Math.min(100, ((soilMoisture - wiltingPoint) / awc) * 100))
      : 0;

  const handleSoilTypePreset = (name: string) => {
    onSoilTypeChange(name);
    const matched = SOIL_TYPES.find((s) => s.name === name);
    if (matched && name !== 'Custom Soil') {
      onFieldCapacityChange(matched.fc);
      onWiltingPointChange(matched.wp);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-amber-500/10 text-amber-400 rounded-lg">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Soil Hydrology Parameters</h3>
            <p className="text-xs text-slate-400">
              Soil moisture deficit, permanent wilting point, and field capacity matrix.
            </p>
          </div>
        </div>
        <span className="text-[10px] font-mono tracking-wide px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/80 text-blue-300">
          SIMULATED / VIRTUAL DATA
        </span>
      </div>

      {/* Bounds Validation Warning */}
      {isInvalidBounds && (
        <div className="mb-4 p-3 bg-rose-950/40 border border-rose-600/80 rounded-lg flex items-start gap-2.5 text-rose-200 text-xs">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Hydrological Inconsistency Detected: </span>
            Field Capacity ({fieldCapacity}%) must be strictly greater than Wilting Point ({wiltingPoint}%).
            Please correct these limits to proceed.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Soil Type Selection */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Soil Texture Class
          </label>
          <select
            value={soilType}
            onChange={(e) => handleSoilTypePreset(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-500"
          >
            {SOIL_TYPES.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} (FC: {s.fc}%, WP: {s.wp}%)
              </option>
            ))}
          </select>
          <div className="mt-1 text-[11px] text-slate-400">
            AWC: <span className="font-mono text-amber-300 font-semibold">{awc.toFixed(1)}%</span> available water
          </div>
        </div>

        {/* Volumetric Soil Moisture */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-slate-300">
              Current Moisture (θ)
            </label>
            <span className="font-mono text-xs font-bold text-amber-300">
              {soilMoisture.toFixed(1)}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="60"
            step="0.5"
            value={soilMoisture}
            onChange={(e) => onSoilMoistureChange(Number(e.target.value))}
            className="w-full accent-amber-500 h-1.5 bg-slate-700 rounded-lg cursor-pointer"
          />
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span>0% (Bone Dry)</span>
            <span>
              {soilMoisture < wiltingPoint ? (
                <span className="text-rose-400 font-semibold">Below Wilting Pt</span>
              ) : soilMoisture > fieldCapacity ? (
                <span className="text-blue-400 font-semibold">Above Field Cap</span>
              ) : (
                <span className="text-emerald-400 font-semibold">{currentAvailablePct.toFixed(0)}% AWC</span>
              )}
            </span>
            <span>60% (Saturated)</span>
          </div>
        </div>

        {/* Field Capacity */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Field Capacity (FC) %
          </label>
          <input
            type="number"
            min="5"
            max="60"
            step="0.5"
            value={fieldCapacity}
            onChange={(e) => onFieldCapacityChange(Number(e.target.value))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
          <div className="mt-1 text-[11px] text-slate-400">
            Upper storage limit before gravitational drainage.
          </div>
        </div>

        {/* Wilting Point */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Permanent Wilting Point (WP) %
          </label>
          <input
            type="number"
            min="0"
            max="40"
            step="0.5"
            value={wiltingPoint}
            onChange={(e) => onWiltingPointChange(Number(e.target.value))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
          <div className="mt-1 text-[11px] text-slate-400">
            Lower extraction threshold; plant wilt occurs.
          </div>
        </div>
      </div>
    </div>
  );
};
