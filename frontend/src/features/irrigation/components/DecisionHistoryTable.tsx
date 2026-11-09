import React from 'react';
import type { IrrigationHistoryRecord } from '../types';
import { History } from 'lucide-react';

interface Props {
  history: IrrigationHistoryRecord[];
  isLoading: boolean;
}

export const DecisionHistoryTable: React.FC<Props> = ({
  history,
  isLoading,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-sky-500/10 text-sky-400 rounded-lg">
            <History className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Decision Execution Audit History</h3>
            <p className="text-xs text-slate-400">
              Persistent execution records stored in PostgreSQL database.
            </p>
          </div>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {history.length} record(s) logged
        </span>
      </div>

      {isLoading ? (
        <div className="p-8 text-center text-xs text-slate-400">
          <div className="w-5 h-5 border-2 border-slate-600 border-t-sky-400 rounded-full animate-spin mx-auto mb-2" />
          Querying historical decision logs...
        </div>
      ) : history.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500">
          No previous irrigation executions found for this zone. Execute a workflow run above.
        </div>
      ) : (
        <div className="border border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-800/80 text-slate-400 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-700">
              <tr>
                <th className="p-2.5">Timestamp</th>
                <th className="p-2.5">Decision</th>
                <th className="p-2.5">Rec Depth</th>
                <th className="p-2.5">Soil θ</th>
                <th className="p-2.5">ET₀ (mm/d)</th>
                <th className="p-2.5">Confidence</th>
                <th className="p-2.5">Agronomic Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {history.map((h) => {
                const isReq = h.decision === 'REQUIRED';
                const isPost = h.decision === 'POSTPONED';
                return (
                  <tr key={h.id} className="hover:bg-slate-800/50 transition-colors">
                    <td className="p-2.5 text-slate-400 whitespace-nowrap">
                      {h.scheduled_at ? new Date(h.scheduled_at).toLocaleString() : '—'}
                    </td>
                    <td className="p-2.5 font-sans font-bold">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold inline-flex items-center gap-1 ${
                          isReq
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : isPost
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                        }`}
                      >
                        {h.decision}
                      </span>
                    </td>
                    <td className="p-2.5 text-slate-200">
                      {(h.recommended_volume_mm ?? 0).toFixed(1)} mm
                    </td>
                    <td className="p-2.5 text-amber-300">
                      {h.soil_moisture_before_pct !== null && h.soil_moisture_before_pct !== undefined
                        ? `${h.soil_moisture_before_pct.toFixed(1)}%`
                        : '—'}
                    </td>
                    <td className="p-2.5 text-sky-300">
                      {h.et0_on_day_mm !== null && h.et0_on_day_mm !== undefined
                        ? `${h.et0_on_day_mm.toFixed(2)}`
                        : '—'}
                    </td>
                    <td className="p-2.5 text-emerald-400 font-semibold">
                      {h.decision_confidence !== null && h.decision_confidence !== undefined
                        ? `${(h.decision_confidence * 100).toFixed(0)}%`
                        : '95%'}
                    </td>
                    <td className="p-2.5 font-sans text-slate-300 max-w-xs truncate" title={h.reasoning_summary || ''}>
                      {h.reasoning_summary || 'Autonomous LangGraph scheduling run.'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
