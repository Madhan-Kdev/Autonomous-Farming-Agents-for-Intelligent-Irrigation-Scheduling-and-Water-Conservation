import React from 'react';
import type { CropOut } from '../types';
import { Sprout, Info } from 'lucide-react';

interface Props {
  crops: CropOut[];
  cropType: string;
  onCropTypeChange: (val: string) => void;
  growthStage: 'initial' | 'development' | 'mid' | 'late';
  onGrowthStageChange: (val: 'initial' | 'development' | 'mid' | 'late') => void;
}

export const CropInputsSection: React.FC<Props> = ({
  crops,
  cropType,
  onCropTypeChange,
  growthStage,
  onGrowthStageChange,
}) => {
  const selectedCrop = crops.find(
    (c) => c.name.toLowerCase() === cropType.toLowerCase()
  );

  const getKcForStage = () => {
    if (!selectedCrop) return null;
    switch (growthStage) {
      case 'initial':
        return selectedCrop.kc_initial;
      case 'development':
        return ((selectedCrop.kc_initial + selectedCrop.kc_mid) / 2).toFixed(2);
      case 'mid':
        return selectedCrop.kc_mid;
      case 'late':
        return selectedCrop.kc_end;
    }
  };

  const currentKc = getKcForStage();

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg">
          <Sprout className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Crop & Phenological Parameters</h3>
          <p className="text-xs text-slate-400">
            FAO-56 single-crop coefficient (Kc) and developmental rooting depth calibration.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Crop Selection */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Target Crop Species
          </label>
          <select
            value={cropType}
            onChange={(e) => onCropTypeChange(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            {crops.length > 0 ? (
              crops.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name} {c.scientific_name ? `(${c.scientific_name})` : ''} — Kc: {c.kc_initial} → {c.kc_mid} → {c.kc_end}
                </option>
              ))
            ) : (
              <>
                <option value="Wheat">Wheat (Triticum aestivum)</option>
                <option value="Tomato">Tomato (Solanum lycopersicum)</option>
                <option value="Maize">Maize (Zea mays)</option>
                <option value="Potato">Potato (Solanum tuberosum)</option>
              </>
            )}
          </select>
          {selectedCrop && (
            <div className="mt-1.5 text-[11px] text-slate-400 flex flex-wrap gap-2">
              <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                Max Root: {selectedCrop.root_depth_max_m}m
              </span>
              <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                Depletion (p): {selectedCrop.depletion_fraction_p}
              </span>
              <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                Cycle: {selectedCrop.total_growing_days}d
              </span>
            </div>
          )}
        </div>

        {/* Growth Stage Selection */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Phenological Growth Stage
          </label>
          <div className="grid grid-cols-4 gap-1.5">
            {(
              [
                { id: 'initial', label: 'Initial', desc: 'Germination & seedling' },
                { id: 'development', label: 'Development', desc: 'Vegetative growth' },
                { id: 'mid', label: 'Mid-Season', desc: 'Peak flowering / fruit' },
                { id: 'late', label: 'Late Season', desc: 'Ripening / harvest' },
              ] as const
            ).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onGrowthStageChange(s.id)}
                className={`p-2 rounded-lg text-center transition-all border ${
                  growthStage === s.id
                    ? 'bg-emerald-950/40 border-emerald-500 text-emerald-300 font-semibold ring-1 ring-emerald-500/50'
                    : 'bg-slate-800/60 border-slate-700/60 hover:bg-slate-800 text-slate-300'
                }`}
              >
                <div className="text-xs">{s.label}</div>
                <div className="text-[10px] text-slate-400 hidden sm:block truncate">{s.desc}</div>
              </button>
            ))}
          </div>

          <div className="mt-2 flex items-center justify-between text-xs bg-slate-800/40 border border-slate-800 rounded-lg px-2.5 py-1.5">
            <span className="text-slate-400 flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-emerald-400" />
              Active FAO-56 Crop Coefficient ($K_c$):
            </span>
            <span className="font-mono font-bold text-emerald-300">
              {currentKc !== null ? currentKc : '—'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
