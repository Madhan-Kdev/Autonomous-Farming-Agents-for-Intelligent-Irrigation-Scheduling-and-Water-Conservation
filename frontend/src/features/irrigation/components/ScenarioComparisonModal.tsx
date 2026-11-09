import type { DetailedAgentState } from '../types';
import { X, GitCompare } from 'lucide-react';

interface Props {
  runA: DetailedAgentState | null;
  runB: DetailedAgentState | null;
  onClose: () => void;
}

export const ScenarioComparisonModal: React.FC<Props> = ({ runA, runB, onClose }) => {
  if (!runA || !runB) return null;

  const rows = [
    {
      label: 'Decision Action',
      valA: runA.irrigation_decision?.decision || '—',
      valB: runB.irrigation_decision?.decision || '—',
    },
    {
      label: 'Priority',
      valA: runA.irrigation_decision?.priority || '—',
      valB: runB.irrigation_decision?.priority || '—',
    },
    {
      label: 'Recommended Volume (mm)',
      valA: `${(runA.irrigation_decision?.recommended_volume_mm ?? 0).toFixed(1)} mm`,
      valB: `${(runB.irrigation_decision?.recommended_volume_mm ?? 0).toFixed(1)} mm`,
    },
    {
      label: 'Reference ET0 (FAO-56)',
      valA: `${(runA.et0?.et0_reference_mm ?? 0).toFixed(2)} mm/d`,
      valB: `${(runB.et0?.et0_reference_mm ?? 0).toFixed(2)} mm/d`,
    },
    {
      label: 'ML Predicted ET0 (GBR)',
      valA: `${(runA.et0?.et0_predicted_mm ?? 0).toFixed(2)} mm/d`,
      valB: `${(runB.et0?.et0_predicted_mm ?? 0).toFixed(2)} mm/d`,
    },
    {
      label: 'Soil Moisture (θ)',
      valA: `${(runA.soil?.soil_moisture_pct ?? 0).toFixed(1)}%`,
      valB: `${(runB.soil?.soil_moisture_pct ?? 0).toFixed(1)}%`,
    },
    {
      label: 'Crop Stress Index',
      valA: `${(runA.soil?.soil_stress_index ?? 0).toFixed(2)}`,
      valB: `${(runB.soil?.soil_stress_index ?? 0).toFixed(2)}`,
    },
    {
      label: 'Water Conserved %',
      valA: `${(runA.optimization?.water_saving_pct ?? 0).toFixed(1)}%`,
      valB: `${(runB.optimization?.water_saving_pct ?? 0).toFixed(1)}%`,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative animate-in fade-in zoom-in duration-200">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-100 p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-xl">
            <GitCompare className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-100">Scenario Output Differential</h3>
            <p className="text-xs text-slate-400">
              Comparative matrix demonstrating how changing input parameters dynamically drives model outputs.
            </p>
          </div>
        </div>

        <div className="border border-slate-800 rounded-xl overflow-hidden mb-4">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-800/80 text-slate-300 uppercase tracking-wider font-semibold border-b border-slate-700">
              <tr>
                <th className="p-3">Parameter / Model Output</th>
                <th className="p-3 text-sky-300">Run A ({runA.run_id.slice(0, 8)})</th>
                <th className="p-3 text-emerald-300">Run B ({runB.run_id.slice(0, 8)})</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-slate-800/40">
                  <td className="p-3 font-sans text-slate-300 font-medium">{r.label}</td>
                  <td className="p-3 text-slate-200">{r.valA}</td>
                  <td className="p-3 text-emerald-300 font-bold">{r.valB}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-lg transition-colors"
          >
            Close Comparison
          </button>
        </div>
      </div>
    </div>
  );
};
