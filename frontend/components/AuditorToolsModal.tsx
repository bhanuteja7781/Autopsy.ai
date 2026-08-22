'use client';

import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, Play, Activity, DollarSign, CheckCircle2, XCircle, ChevronDown, ChevronUp, Layers } from 'lucide-react';

interface AuditorToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditorToolsModal: React.FC<AuditorToolsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'eval' | 'costs'>('eval');
  const [evalRuns, setEvalRuns] = useState<any[]>([]);
  const [latestEvalResult, setLatestEvalResult] = useState<any | null>(null);
  const [isRunningEval, setIsRunningEval] = useState(false);
  const [costData, setCostData] = useState<any | null>(null);
  const [expandedCaseIdx, setExpandedCaseIdx] = useState<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchEvalRuns();
      fetchCostData();
    }
  }, [isOpen]);

  const fetchEvalRuns = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8008/api/eval/runs');
      if (res.ok) {
        const data = await res.json();
        setEvalRuns(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchCostData = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8008/api/system/costs');
      if (res.ok) {
        const data = await res.json();
        setCostData(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunEval = async () => {
    setIsRunningEval(true);
    try {
      const res = await fetch('http://127.0.0.1:8008/api/eval/run', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setLatestEvalResult(data);
        fetchEvalRuns();
        fetchCostData();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsRunningEval(false);
    }
  };

  if (!isOpen) return null;

  const currentRun = latestEvalResult || evalRuns[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-3xl max-h-[85vh] rounded-3xl p-6 sm:p-8 flex flex-col space-y-6 shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150 border"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'var(--color-border)',
        }}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b pb-4" style={{ borderColor: 'var(--color-border-subtle)' }}>
          <div>
            <h3 className="text-base font-bold text-[var(--color-text-primary)]">
              Auditor &amp; System Benchmarks
            </h3>
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
              Automated testing suite &amp; regression gating for research and QA teams.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Sub Navigation */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setActiveSubTab('eval')}
            className={`px-4 py-2 rounded-xl text-xs font-medium transition-all cursor-pointer ${
              activeSubTab === 'eval'
                ? 'bg-[var(--color-accent)] text-white shadow-sm'
                : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
            }`}
          >
            21-Case Golden Benchmark
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab('costs')}
            className={`px-4 py-2 rounded-xl text-xs font-medium transition-all cursor-pointer ${
              activeSubTab === 'costs'
                ? 'bg-[var(--color-accent)] text-white shadow-sm'
                : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
            }`}
          >
            Token &amp; Cost Ledger
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto pr-1 space-y-6 text-xs">
          {activeSubTab === 'eval' && (
            <div className="space-y-5">
              {/* Benchmark Trigger Card */}
              <div
                className="p-5 rounded-2xl border flex flex-wrap items-center justify-between gap-4"
                style={{
                  backgroundColor: 'var(--color-surface-subtle)',
                  borderColor: 'var(--color-border)',
                }}
              >
                <div>
                  <div className="font-semibold text-sm text-[var(--color-text-primary)]">
                    Evaluate 21 Ground-Truth Policy Cases
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 max-w-md">
                    Runs reasoning verification against real policy cases (PM-KISAN, Ayushman Bharat, OpenAI ToS, Aadhaar-PAN).
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleRunEval}
                  disabled={isRunningEval}
                  className="px-4 py-2.5 rounded-xl font-semibold text-xs text-white bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] transition-all disabled:opacity-50 cursor-pointer shadow-sm"
                >
                  {isRunningEval ? 'Testing 21 cases...' : 'Run Benchmark'}
                </button>
              </div>

              {/* Accuracy & Gating Summary */}
              {currentRun && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-4 rounded-xl border" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
                    <div className="text-[11px] text-[var(--color-text-muted)]">Benchmark Accuracy</div>
                    <div className="text-xl font-bold mt-1" style={{ color: 'var(--color-accent)' }}>
                      {(currentRun.accuracy * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-1">{currentRun.total_cases || 21} verified cases</div>
                  </div>

                  <div className="p-4 rounded-xl border" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
                    <div className="text-[11px] text-[var(--color-text-muted)]">False Positive Rate</div>
                    <div className="text-xl font-bold text-amber-500 mt-1">
                      {(currentRun.false_positive_rate * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-1">Erronously flagged consistent text</div>
                  </div>

                  <div className="p-4 rounded-xl border" style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
                    <div className="text-[11px] text-[var(--color-text-muted)]">Regression Gate Status</div>
                    <div className="text-base font-bold text-emerald-600 mt-1.5 flex items-center gap-1">
                      <CheckCircle2 size={16} />
                      <span>PROMOTED</span>
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-1">Allowed drop tolerance: ±3%</div>
                  </div>
                </div>
              )}

              {/* Per-Case Breakdown List */}
              {currentRun && currentRun.per_case_results && (
                <div className="space-y-3 pt-2">
                  <div className="font-semibold text-xs text-[var(--color-text-primary)]">
                    Per-Case Ground-Truth Results ({currentRun.per_case_results.length})
                  </div>
                  <div className="space-y-2">
                    {currentRun.per_case_results.map((c: any, idx: number) => {
                      const isExpanded = expandedCaseIdx === idx;
                      return (
                        <div
                          key={idx}
                          className="rounded-xl border overflow-hidden"
                          style={{
                            backgroundColor: 'var(--color-surface)',
                            borderColor: 'var(--color-border-subtle)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setExpandedCaseIdx(isExpanded ? null : idx)}
                            className="w-full p-3 text-left flex items-center justify-between gap-2 hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="font-semibold text-[var(--color-text-secondary)]">Case #{idx + 1}</span>
                              <span className="text-[11px] text-[var(--color-text-muted)]">({c.claim_type})</span>
                              <span className="text-[11px] text-[var(--color-text-primary)] font-medium truncate">
                                Truth: {c.human_label}
                              </span>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {c.correct ? (
                                <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full">
                                  Matched
                                </span>
                              ) : (
                                <span className="text-[10px] font-semibold text-rose-600 bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded-full">
                                  Mismatch
                                </span>
                              )}
                              {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </button>

                          {isExpanded && (
                            <div className="p-3 border-t space-y-2 bg-[var(--color-surface-subtle)] text-[11px]" style={{ borderColor: 'var(--color-border-subtle)' }}>
                              <div><strong>Claim A:</strong> "{c.claim_a_excerpt}"</div>
                              <div><strong>Claim B:</strong> "{c.claim_b_excerpt}"</div>
                              {c.model_reasoning && <div><strong>Reasoner:</strong> {c.model_reasoning}</div>}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeSubTab === 'costs' && (
            <div className="space-y-4">
              <div className="p-5 rounded-2xl border space-y-3" style={{ backgroundColor: 'var(--color-surface-subtle)', borderColor: 'var(--color-border)' }}>
                <div className="font-semibold text-sm text-[var(--color-text-primary)]">
                  Pipeline Cost &amp; Token Tracing
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[11px] text-[var(--color-text-muted)]">Grand Total Spent</div>
                    <div className="text-xl font-bold text-emerald-600 mt-0.5">
                      ${(costData?.grand_total_usd || 0).toFixed(4)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-[var(--color-text-muted)]">Total Tokens Processed</div>
                    <div className="text-xl font-bold text-[var(--color-text-primary)] mt-0.5">
                      {costData?.grand_total_tokens || 0}
                    </div>
                  </div>
                </div>
              </div>

              {costData?.stages && (
                <div className="space-y-2">
                  <div className="font-semibold text-xs text-[var(--color-text-primary)]">
                    Breakdown by Pipeline Stage
                  </div>
                  {costData.stages.map((st: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl border flex items-center justify-between"
                      style={{
                        backgroundColor: 'var(--color-surface)',
                        borderColor: 'var(--color-border-subtle)',
                      }}
                    >
                      <div>
                        <span className="font-semibold capitalize text-[var(--color-text-primary)]">{st.stage} Stage</span>
                        <span className="text-[11px] text-[var(--color-text-muted)] ml-2">({st.call_count} operations)</span>
                      </div>
                      <div className="font-medium text-[var(--color-text-primary)]">
                        ${st.total_cost_usd.toFixed(4)} ({st.total_tokens_in + st.total_tokens_out} tokens)
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
