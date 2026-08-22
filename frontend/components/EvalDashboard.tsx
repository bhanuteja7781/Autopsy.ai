'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Play, Activity, AlertOctagon, CheckCircle2, XCircle, ChevronDown, ChevronUp, Layers } from 'lucide-react';

export const EvalDashboard: React.FC = () => {
  const [runs, setRuns] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [latestResult, setLatestResult] = useState<any>(null);
  const [expandedCaseIndex, setExpandedCaseIndex] = useState<number | null>(null);

  const fetchRuns = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8008/api/eval/runs');
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleRunEval = async () => {
    setIsRunning(true);
    try {
      const res = await fetch('http://127.0.0.1:8008/api/eval/run', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setLatestResult(data);
        fetchRuns();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsRunning(false);
    }
  };

  const latestRun = runs[0] || latestResult;

  return (
    <div className="space-y-6">
      {/* Top Header & Run Trigger */}
      <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold text-slate-100">
              Evaluation Harness &amp; Regression Gate
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Automated testing against 21 hand-labeled ground-truth policy cases. Gating prevents prompt or model regression before production deployment.
          </p>
        </div>

        <button
          onClick={handleRunEval}
          disabled={isRunning}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-black font-semibold text-xs transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50 cursor-pointer"
        >
          <Play className={`w-3.5 h-3.5 fill-current ${isRunning ? 'animate-spin' : ''}`} />
          <span>{isRunning ? 'Running 21 Eval Cases...' : 'Execute Eval Suite'}</span>
        </button>
      </div>

      {/* Primary KPI Metrics */}
      {latestRun && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Accuracy */}
          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Benchmark Accuracy
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-300">
              {(latestRun.accuracy * 100).toFixed(1)}%
            </div>
            <p className="text-[10px] text-slate-500">
              Evaluated across {latestRun.total_cases || 21} hand-labeled cases
            </p>
          </div>

          {/* False Positive Rate */}
          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              False Positive Rate
            </div>
            <div className="text-2xl font-bold font-mono text-amber-300">
              {(latestRun.false_positive_rate * 100).toFixed(1)}%
            </div>
            <p className="text-[10px] text-slate-500">
              Consistent text erroneously flagged as contradiction
            </p>
          </div>

          {/* False Negative Rate */}
          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              False Negative Rate
            </div>
            <div className="text-2xl font-bold font-mono text-cyan-300">
              {(latestRun.false_negative_rate * 100).toFixed(1)}%
            </div>
            <p className="text-[10px] text-slate-500">
              Real silent contradictions missed by reasoner
            </p>
          </div>
        </div>
      )}

      {/* Historical Runs Table */}
      <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
            Historical Eval Runs &amp; Promotion Gates
          </h3>
          <span className="text-[10px] text-slate-400 font-mono">
            Regression Tolerance: ±3%
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs font-sans">
            No eval runs recorded yet. Click "Execute Eval Suite" above to benchmark.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[10px]">
                  <th className="pb-2">Timestamp</th>
                  <th className="pb-2">Model Version</th>
                  <th className="pb-2">Cases</th>
                  <th className="pb-2">Accuracy</th>
                  <th className="pb-2">FP Rate</th>
                  <th className="pb-2">FN Rate</th>
                  <th className="pb-2">Promotion Gate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {runs.map((r, i) => (
                  <tr key={i} className="hover:bg-[#0E1524]/60 transition-colors">
                    <td className="py-2.5 text-slate-300">
                      {new Date(r.run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="py-2.5 text-slate-400 truncate max-w-[140px]">
                      {r.reasoner_model_version}
                    </td>
                    <td className="py-2.5 text-slate-300">{r.total_cases}</td>
                    <td className="py-2.5 text-emerald-300 font-bold">
                      {(r.accuracy * 100).toFixed(1)}%
                    </td>
                    <td className="py-2.5 text-amber-300 font-bold">
                      {(r.false_positive_rate * 100).toFixed(1)}%
                    </td>
                    <td className="py-2.5 text-cyan-300 font-bold">
                      {(r.false_negative_rate * 100).toFixed(1)}%
                    </td>
                    <td className="py-2.5">
                      {r.promoted_to_production ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 font-bold">
                          PROMOTED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-red-950/80 text-red-300 border border-red-500/40 font-bold">
                          BLOCKED
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Per-Case Breakdown Table as per DPR §6.2 */}
      {latestRun && latestRun.per_case_results && (
        <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
              Per-Case Golden Benchmark Breakdown ({latestRun.per_case_results.length})
            </h3>
            <span className="text-[10px] text-slate-400 font-mono">
              Click any row to reveal excerpts &amp; model reasoning
            </span>
          </div>

          <div className="space-y-2">
            {latestRun.per_case_results.map((c: any, idx: number) => {
              const isExpanded = expandedCaseIndex === idx;
              return (
                <div key={idx} className="border border-slate-800/80 rounded-xl bg-[#080B12] overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setExpandedCaseIndex(isExpanded ? null : idx)}
                    className="w-full flex items-center justify-between p-3 text-left hover:bg-[#0E1524]/60 transition-colors gap-3 cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="text-[11px] font-mono text-cyan-400 font-bold">
                        CASE #{idx + 1}
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {c.claim_type || 'eligibility'}
                      </span>
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                        c.human_label === 'silent_contradiction' ? 'bg-red-950 text-red-300 border border-red-500/30' :
                        c.human_label === 'explicit_update' ? 'bg-blue-950 text-blue-300 border border-blue-500/30' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        Truth: {c.human_label}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        Model: <strong className="text-slate-200">{c.model_label}</strong> ({(c.model_confidence * 100).toFixed(0)}%)
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {c.correct ? (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">
                          <CheckCircle2 size={11} /> MATCH
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-red-400 bg-red-950/60 border border-red-500/30 px-2 py-0.5 rounded-full font-bold">
                          <XCircle size={11} /> MISMATCH
                        </span>
                      )}
                      {isExpanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-slate-800 p-4 space-y-3 bg-[#0B0F19]/90 text-xs animate-in fade-in duration-150">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-sans">
                        <div className="p-3 rounded-lg bg-[#0E2A3A]/40 border border-cyan-500/20 space-y-1">
                          <div className="text-[10px] font-mono text-cyan-400 uppercase font-bold">Claim A Excerpt</div>
                          <blockquote className="text-slate-300 text-[11px] leading-relaxed">
                            "{c.claim_a_excerpt}"
                          </blockquote>
                        </div>
                        <div className="p-3 rounded-lg bg-[#33200A]/40 border border-amber-500/20 space-y-1">
                          <div className="text-[10px] font-mono text-amber-400 uppercase font-bold">Claim B Excerpt</div>
                          <blockquote className="text-slate-300 text-[11px] leading-relaxed">
                            "{c.claim_b_excerpt}"
                          </blockquote>
                        </div>
                      </div>

                      {c.model_reasoning && (
                        <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 font-sans">
                          <strong className="text-slate-200">Reasoner Plain-Language Grounding:</strong> {c.model_reasoning}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
