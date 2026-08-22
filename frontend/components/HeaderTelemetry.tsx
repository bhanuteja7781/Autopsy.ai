'use client';

import React from 'react';
import { DollarSign, ShieldCheck, Activity, Database, CheckSquare, Layers } from 'lucide-react';

interface HeaderTelemetryProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  reviewCount: number;
  totalCostUsd?: number;
  onOpenCostDrawer?: () => void;
}

export const HeaderTelemetry: React.FC<HeaderTelemetryProps> = ({
  activeTab,
  setActiveTab,
  reviewCount,
  totalCostUsd = 0.042,
  onOpenCostDrawer,
}) => {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-800 bg-[#080B12]/90 backdrop-blur-md px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400 font-mono font-bold text-xs shadow-lg shadow-cyan-500/10">
            A
          </div>
          <div>
            <span className="font-bold text-sm text-slate-100 tracking-tight">autopsy.ai</span>
            <span className="text-[10px] text-cyan-400 font-mono ml-2 border border-cyan-500/30 px-1.5 py-0.5 rounded bg-cyan-950/40">
              POLICY DRIFT FORENSICS
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1.5 bg-[#0B0F19] p-1 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('workspace')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
              activeTab === 'workspace'
                ? 'bg-cyan-500 text-black font-semibold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Investigation Workspace
          </button>

          <button
            onClick={() => setActiveTab('review')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'review'
                ? 'bg-cyan-500 text-black font-semibold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Review Queue (HITL)</span>
            {reviewCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-400 text-black font-bold">
                {reviewCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('corpus')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
              activeTab === 'corpus'
                ? 'bg-cyan-500 text-black font-semibold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Corpus Manager
          </button>

          <button
            onClick={() => setActiveTab('eval')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
              activeTab === 'eval'
                ? 'bg-cyan-500 text-black font-semibold shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Eval Dashboard
          </button>
        </nav>

        {/* Telemetry Cost & Status Counter */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenCostDrawer}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-800 bg-[#0B0F19] text-[11px] font-mono text-slate-300 hover:border-slate-700 transition-all cursor-pointer"
            title="Inspect Cost Ledger & Audit Trail"
          >
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span>${totalCostUsd.toFixed(4)}</span>
            <span className="text-[10px] text-slate-500">LEDGER</span>
          </button>
        </div>
      </div>
    </header>
  );
};
