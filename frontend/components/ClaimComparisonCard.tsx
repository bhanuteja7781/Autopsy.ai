'use client';

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Info, CheckCircle2, XCircle, ExternalLink } from "lucide-react";

export type Verdict = "consistent" | "explicit_update" | "silent_contradiction" | "insufficient_evidence";

export interface ClaimSide {
  excerpt: string;
  sourceUrl: string;
  publishedAt: string | null;
  claimType?: string;
}

export interface ClaimComparisonCardProps {
  comparisonId: string;
  verdict: Verdict;
  confidence: number; // 0-1
  reasoning: string;
  claimA: ClaimSide;
  claimB: ClaimSide;
  impactLevel?: string;
  impactScore?: number;
  impactCategory?: string;
  impactSummary?: string;
  onReview?: (comparisonId: string, action: "confirmed" | "dismissed") => void;
  latestReviewAction?: string | null;
}

const VERDICT_STYLES: Record<Verdict, { label: string; pillClass: string }> = {
  consistent: { label: "Consistent", pillClass: "bg-slate-800 text-slate-300 border border-slate-700" },
  explicit_update: { label: "Explicit Update", pillClass: "bg-blue-950/80 text-blue-300 border border-blue-500/40" },
  silent_contradiction: { label: "Silent Contradiction", pillClass: "bg-red-950/90 text-red-300 border border-red-500/50 font-bold" },
  insufficient_evidence: { label: "Insufficient Evidence", pillClass: "bg-amber-950/80 text-amber-300 border border-amber-500/40" },
};

function getImpactBadge(level: string = "HIGH", score: number = 0.8) {
  const l = (level || "HIGH").toUpperCase();
  if (l === "CRITICAL") {
    return {
      label: "CRITICAL",
      className: "bg-rose-950/90 text-rose-300 border border-rose-500/60 font-bold",
    };
  }
  if (l === "HIGH") {
    return {
      label: "HIGH IMPACT",
      className: "bg-amber-950/80 text-amber-300 border border-amber-500/50",
    };
  }
  if (l === "MEDIUM") {
    return {
      label: "MED IMPACT",
      className: "bg-blue-950/70 text-blue-300 border border-blue-500/40",
    };
  }
  return {
    label: "LOW",
    className: "bg-slate-800 text-slate-400 border border-slate-700",
  };
}

function ConfidencePill({ confidence }: { confidence: number }) {
  const [showInfo, setShowInfo] = useState(false);
  const pct = Math.round(confidence * 100);
  const tone =
    confidence >= 0.85 ? "bg-emerald-950/80 text-emerald-300 border border-emerald-500/40" :
    confidence >= 0.6 ? "bg-amber-950/80 text-amber-300 border border-amber-500/40" :
    "bg-slate-800 text-slate-400 border border-slate-700";

  return (
    <div className="relative inline-flex items-center gap-1">
      <span className={`text-[11px] font-mono font-medium px-2 py-0.5 rounded-full ${tone}`}>
        {pct}% confidence
      </span>
      <button
        type="button"
        aria-label="What does confidence mean?"
        onMouseEnter={() => setShowInfo(true)}
        onMouseLeave={() => setShowInfo(false)}
        onClick={() => setShowInfo((s) => !s)}
        className="text-slate-400 hover:text-slate-200 transition-colors"
      >
        <Info size={13} />
      </button>
      {showInfo && (
        <div className="absolute z-20 top-6 left-0 w-60 text-[11px] bg-slate-900 border border-slate-700 text-slate-200 rounded-lg p-2.5 shadow-2xl leading-relaxed animate-in fade-in duration-150">
          Calibrated against verified historical cases. Below 60% is routed to human review before being shown as a primary flag.
        </div>
      )}
    </div>
  );
}

function ExcerptColumn({ label, claim, isEarlier }: { label: string; claim: ClaimSide; isEarlier: boolean }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-[10px] uppercase tracking-wider font-mono font-bold ${isEarlier ? 'text-cyan-400' : 'text-amber-400'}`}>
          {label}
        </span>
        <span className="text-[10px] text-slate-400 font-mono">{claim.publishedAt ?? "Date unknown"}</span>
      </div>
      <blockquote className={`text-xs text-slate-200 leading-relaxed p-3 rounded-lg border select-text ${
        isEarlier 
          ? 'bg-[#0E2A3A]/60 border-cyan-500/30' 
          : 'bg-[#33200A]/60 border-amber-500/30'
      }`}>
        "{claim.excerpt}"
      </blockquote>
      <a
        href={claim.sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1.5 inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-cyan-300 font-mono transition-colors"
      >
        <span>Source link</span>
        <ExternalLink size={10} />
      </a>
    </div>
  );
}

export default function ClaimComparisonCard({
  comparisonId,
  verdict,
  confidence,
  reasoning,
  claimA,
  claimB,
  impactLevel = "HIGH",
  impactScore = 0.80,
  impactCategory,
  impactSummary,
  onReview,
  latestReviewAction,
}: ClaimComparisonCardProps) {
  const [expanded, setExpanded] = useState(false);
  const verdictStyle = VERDICT_STYLES[verdict] || VERDICT_STYLES.consistent;
  const impactStyle = getImpactBadge(impactLevel, impactScore);

  return (
    <div className={`rounded-xl border transition-all ${
      verdict === 'silent_contradiction' 
        ? 'border-red-500/40 bg-[#0E121E] hover:border-red-500/60' 
        : 'border-slate-800 bg-[#0B0F19] hover:border-slate-700'
    }`}>
      {/* Collapsed row header — high density single line */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-4 py-3 text-left gap-3"
      >
        <div className="flex items-center gap-2 min-w-0 flex-1 flex-wrap sm:flex-nowrap">
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full whitespace-nowrap ${impactStyle.className}`}>
            {impactStyle.label}
          </span>
          <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full whitespace-nowrap ${verdictStyle.pillClass}`}>
            {verdictStyle.label}
          </span>
          <ConfidencePill confidence={confidence} />
          {impactCategory && (
            <span className="hidden md:inline-block text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
              {impactCategory}
            </span>
          )}
          <span className="text-xs text-slate-300 truncate font-sans">{reasoning}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {latestReviewAction && (
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
              latestReviewAction === 'confirmed' ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-400'
            }`}>
              {latestReviewAction.toUpperCase()}
            </span>
          )}
          {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>

      {/* Expanded evidence view — progressive disclosure */}
      {expanded && (
        <div className="border-t border-slate-800/80 px-4 py-4 space-y-4 bg-[#080B12]/80 animate-in fade-in duration-150">
          {impactSummary && (
            <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200 flex items-start gap-2">
              <span className="font-bold uppercase tracking-wider text-[10px] text-amber-400 shrink-0 mt-0.5">Impact:</span>
              <span>{impactSummary}</span>
            </div>
          )}
          <div className="flex flex-col md:flex-row gap-4">
            <ExcerptColumn label="Earlier Statement" claim={claimA} isEarlier={true} />
            <div className="hidden md:block w-px bg-slate-800 self-stretch" />
            <ExcerptColumn label="Later Statement" claim={claimB} isEarlier={false} />
          </div>

          <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between">
            <p className="text-[11px] text-slate-400">
              Classification only — verify original document excerpts before citing publicly.
            </p>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onReview?.(comparisonId, "confirmed")}
                aria-label="Confirm this flag"
                title="Confirm flag"
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-emerald-400 hover:bg-emerald-950/60 border border-emerald-500/30 text-xs font-medium transition-all cursor-pointer"
              >
                <CheckCircle2 size={13} />
                <span>Confirm</span>
              </button>
              <button
                type="button"
                onClick={() => onReview?.(comparisonId, "dismissed")}
                aria-label="Dismiss this flag"
                title="Dismiss flag"
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-slate-400 hover:bg-slate-800/80 border border-slate-700 text-xs font-medium transition-all cursor-pointer"
              >
                <XCircle size={13} />
                <span>Dismiss</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
