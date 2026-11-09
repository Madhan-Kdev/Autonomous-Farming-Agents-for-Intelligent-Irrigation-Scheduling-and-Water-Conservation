import { Droplet } from 'lucide-react';

interface Props {
  waterAvailability: 'Normal' | 'Limited' | 'Low' | 'Critical';
  onWaterAvailabilityChange: (val: 'Normal' | 'Limited' | 'Low' | 'Critical') => void;
  availableWaterLiters: number;
  onAvailableWaterLitersChange: (val: number) => void;
}

export const WaterAvailabilitySection: React.FC<Props> = ({
  waterAvailability,
  onWaterAvailabilityChange,
  availableWaterLiters,
  onAvailableWaterLitersChange,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-cyan-500/10 text-cyan-400 rounded-lg">
          <Droplet className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Water Storage & Resource Availability</h3>
          <p className="text-xs text-slate-400">
            Pumping capacity, tank storage constraints, and deficit quota management.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Availability Status */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Reservoir / Source Status
          </label>
          <div className="grid grid-cols-4 gap-2">
            {(
              [
                { id: 'Normal', label: 'Normal', color: 'border-emerald-500 text-emerald-300 bg-emerald-950/30' },
                { id: 'Limited', label: 'Limited', color: 'border-amber-500 text-amber-300 bg-amber-950/30' },
                { id: 'Low', label: 'Low', color: 'border-orange-500 text-orange-300 bg-orange-950/30' },
                { id: 'Critical', label: 'Critical', color: 'border-rose-500 text-rose-300 bg-rose-950/30' },
              ] as const
            ).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onWaterAvailabilityChange(s.id)}
                className={`p-2 rounded-lg text-center text-xs font-medium transition-all border ${
                  waterAvailability === s.id
                    ? `${s.color} font-bold ring-1`
                    : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="mt-1.5 text-[11px] text-slate-400">
            {waterAvailability === 'Critical'
              ? 'Emergency rationing mode: Optimizer cuts non-essential application volume.'
              : waterAvailability === 'Low'
              ? 'Deficit irrigation mode enabled.'
              : 'Unrestricted optimal irrigation mode.'}
          </div>
        </div>

        {/* Available Liters */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-slate-300">
              Total Usable Water Reserve (Liters)
            </label>
            <span className="font-mono text-xs font-bold text-cyan-400">
              {availableWaterLiters.toLocaleString()} L
            </span>
          </div>
          <input
            type="number"
            min="0"
            max="1000000"
            step="5000"
            value={availableWaterLiters}
            onChange={(e) => onAvailableWaterLitersChange(Number(e.target.value))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          <div className="mt-1.5 flex gap-2">
            {[15000, 50000, 150000, 500000].map((liters) => (
              <button
                key={liters}
                type="button"
                onClick={() => onAvailableWaterLitersChange(liters)}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 font-mono"
              >
                {(liters / 1000).toFixed(0)}k L
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
