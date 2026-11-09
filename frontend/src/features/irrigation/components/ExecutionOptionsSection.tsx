import { Sliders, Play } from 'lucide-react';

interface Props {
  runFullWorkflow: boolean;
  onRunFullWorkflowChange: (val: boolean) => void;
  useEt0Prediction: boolean;
  onUseEt0PredictionChange: (val: boolean) => void;
  useHistoricalData: boolean;
  onUseHistoricalDataChange: (val: boolean) => void;
  userNotes: string;
  onUserNotesChange: (val: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  isInvalidBounds: boolean;
}

export const ExecutionOptionsSection: React.FC<Props> = ({
  runFullWorkflow,
  onRunFullWorkflowChange,
  useEt0Prediction,
  onUseEt0PredictionChange,
  useHistoricalData,
  onUseHistoricalDataChange,
  userNotes,
  onUserNotesChange,
  onSubmit,
  isLoading,
  isInvalidBounds,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-purple-500/10 text-purple-400 rounded-lg">
          <Sliders className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Workflow Execution Architecture</h3>
          <p className="text-xs text-slate-400">
            Configure multi-agent coordination toggles and trigger deterministic LangGraph pipeline.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {/* Run full workflow */}
        <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 cursor-pointer hover:bg-slate-800">
          <input
            type="checkbox"
            checked={runFullWorkflow}
            onChange={(e) => onRunFullWorkflowChange(e.target.checked)}
            className="mt-1 accent-purple-500 rounded"
          />
          <div>
            <div className="text-xs font-semibold text-slate-200">Full 10-Agent Pipeline</div>
            <div className="text-[10px] text-slate-400 leading-tight mt-0.5">
              Execute Master Orchestrator through all 10 domain agents and synthesize final advisory.
            </div>
          </div>
        </label>

        {/* Use ET0 ML Prediction */}
        <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 cursor-pointer hover:bg-slate-800">
          <input
            type="checkbox"
            checked={useEt0Prediction}
            onChange={(e) => onUseEt0PredictionChange(e.target.checked)}
            className="mt-1 accent-purple-500 rounded"
          />
          <div>
            <div className="text-xs font-semibold text-slate-200">ML ET0 Regressor</div>
            <div className="text-[10px] text-slate-400 leading-tight mt-0.5">
              Run GradientBoostingRegressor for short-term evapotranspiration forecasting.
            </div>
          </div>
        </label>

        {/* Use Historical Audit */}
        <label className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 cursor-pointer hover:bg-slate-800">
          <input
            type="checkbox"
            checked={useHistoricalData}
            onChange={(e) => onUseHistoricalDataChange(e.target.checked)}
            className="mt-1 accent-purple-500 rounded"
          />
          <div>
            <div className="text-xs font-semibold text-slate-200">Historical Audit Analysis</div>
            <div className="text-[10px] text-slate-400 leading-tight mt-0.5">
              Compare current deficit against 14-day cumulative irrigation records.
            </div>
          </div>
        </label>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <input
          type="text"
          placeholder="Optional scenario label / research notes (e.g. 'Test high heat with wheat in mid-stage')..."
          value={userNotes}
          onChange={(e) => onUserNotesChange(e.target.value)}
          className="flex-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
        />

        <button
          type="button"
          disabled={isLoading || isInvalidBounds}
          onClick={onSubmit}
          className={`w-full sm:w-auto px-6 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all shadow-md ${
            isInvalidBounds
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
              : isLoading
              ? 'bg-purple-700 text-purple-200 cursor-wait'
              : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white active:scale-[0.99]'
          }`}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Agents Executing (LangGraph)...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Run Multi-Agent Decision Workflow</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
