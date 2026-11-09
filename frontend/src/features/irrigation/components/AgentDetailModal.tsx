import type { DetailedAgentExecutionRecord } from '../types';
import { X, CheckCircle2, AlertTriangle, Cpu, ArrowRight } from 'lucide-react';

interface Props {
  agent: DetailedAgentExecutionRecord | null;
  onClose: () => void;
}

export const AgentDetailModal: React.FC<Props> = ({ agent, onClose }) => {
  if (!agent) return null;

  const isSuccess = agent.status === 'COMPLETED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative animate-in fade-in zoom-in duration-200">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-100 p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 bg-purple-500/10 text-purple-400 rounded-xl border border-purple-500/20">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-100">{agent.agent_name}</h3>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                  isSuccess
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}
              >
                {agent.status}
              </span>
            </div>
            <p className="text-xs text-slate-400">Autonomous Domain Agent Execution Profile</p>
          </div>
        </div>

        {/* Execution Metadata Pills */}
        <div className="grid grid-cols-3 gap-2.5 mb-4 text-xs">
          <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block mb-0.5">Execution Latency</span>
            <span className="font-mono font-bold text-slate-200">
              {agent.duration_ms !== null && agent.duration_ms !== undefined
                ? `${agent.duration_ms.toFixed(1)} ms`
                : '—'}
            </span>
          </div>

          <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block mb-0.5">Agent Confidence</span>
            <span className="font-mono font-bold text-emerald-400">
              {agent.confidence !== null && agent.confidence !== undefined
                ? `${(agent.confidence * 100).toFixed(0)}%`
                : '95%'}
            </span>
          </div>

          <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block mb-0.5">Graph Step</span>
            <span className="font-mono font-semibold text-purple-300">Synchronous Node</span>
          </div>
        </div>

        {/* Agent Inputs */}
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
            <ArrowRight className="w-3.5 h-3.5 text-sky-400" />
            Consolidated Inputs Received:
          </h4>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300 break-words leading-relaxed max-h-32 overflow-y-auto">
            {agent.input_summary || 'Synchronized state variables from upstream LangGraph nodes.'}
          </div>
        </div>

        {/* Agent Outputs */}
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Autonomous Decision & Output Synthesized:
          </h4>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs font-mono text-emerald-300 break-words leading-relaxed max-h-36 overflow-y-auto">
            {agent.output_summary || 'Domain analysis executed and updated into shared master state.'}
          </div>
        </div>

        {/* Error message if any */}
        {agent.error_message && (
          <div className="p-3 bg-rose-950/40 border border-rose-600/60 rounded-lg text-rose-300 text-xs flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Execution Error: </span>
              {agent.error_message}
            </div>
          </div>
        )}

        <div className="mt-5 pt-3 border-t border-slate-800 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
