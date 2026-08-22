'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, Check, X, Info, Sparkles } from 'lucide-react';

export type FindingVerdict = 'silent_contradiction' | 'explicit_update' | 'consistent' | 'insufficient_evidence';

export interface FindingSide {
  excerpt: string;
  sourceUrl: string;
  publishedAt: string | null;
  claimType?: string;
}

export interface PolicyFindingCardProps {
  id: string;
  verdict: FindingVerdict;
  confidence: number;
  reasoning: string;
  claimA: FindingSide;
  claimB: FindingSide;
  onReview?: (id: string, action: 'confirmed' | 'dismissed') => void;
  latestReviewAction?: string | null;
}

export const PolicyFindingCard: React.FC<PolicyFindingCardProps> = ({
  id,
  verdict,
  confidence,
  reasoning,
  claimA,
  claimB,
  onReview,
  latestReviewAction,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  // Verdict pill details
  const getVerdictDetails = () => {
    switch (verdict) {
      case 'silent_contradiction':
        return {
          label: 'Silent Contradiction',
          pillBg: 'var(--color-danger-pill-bg)',
          pillText: 'var(--color-danger-pill-text)',
          cardBorder: 'var(--color-danger-border)',
          cardText: 'var(--color-danger-text)',
          dotColor: '#ef4444',
          tooltip: 'The policy rule was substantively reversed or altered without an official acknowledgement or superseding reference.'
        };
      case 'explicit_update':
        return {
          label: 'Explicit Update',
          pillBg: 'var(--color-info-pill-bg)',
          pillText: 'var(--color-info-pill-text)',
          cardBorder: 'var(--color-info-border)',
          cardText: 'var(--color-info-text)',
          dotColor: '#3b82f6',
          tooltip: 'The later document formally announced and cross-referenced an amendment to the earlier rule.'
        };
      case 'consistent':
        return {
          label: 'Consistent',
          pillBg: 'var(--color-neutral-pill-bg)',
          pillText: 'var(--color-neutral-pill-text)',
          cardBorder: 'var(--color-border)',
          cardText: 'var(--color-neutral-text)',
          dotColor: '#10b981',
          tooltip: 'Both statements convey the same statutory rule, despite slight differences in phrasing.'
        };
      default:
        return {
          label: 'Insufficient Evidence',
          pillBg: 'var(--color-neutral-pill-bg)',
          pillText: 'var(--color-neutral-pill-text)',
          cardBorder: 'var(--color-border)',
          cardText: 'var(--color-neutral-text)',
          dotColor: '#f59e0b',
          tooltip: 'The available document excerpts cannot be compared with high semantic certainty.'
        };
    }
  };

  const vDetails = getVerdictDetails();
  const confidencePct = Math.round(confidence * 100);

  return (
    <article
      className="rounded-2xl transition-all duration-200 overflow-hidden border"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: vDetails.cardBorder,
        boxShadow: 'var(--card-shadow)',
      }}
    >
      {/* Primary Card Header */}
      <div className="p-5 sm:p-6 space-y-3">
        {/* Badges Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {/* Verdict Pill */}
            <span
              className="text-xs font-semibold px-3 py-1 rounded-full flex items-center gap-1.5 shadow-2xs"
              style={{
                backgroundColor: vDetails.pillBg,
                color: vDetails.pillText,
              }}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: vDetails.dotColor }} />
              <span>{vDetails.label}</span>
            </span>

            {/* Calibrated Confidence Badge with Info Tooltip */}
            <div className="relative inline-block">
              <button
                type="button"
                onClick={() => setShowTooltip(!showTooltip)}
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full border flex items-center gap-1 cursor-pointer"
                style={{
                  backgroundColor: 'var(--color-surface-subtle)',
                  borderColor: 'var(--color-border-subtle)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <span>{confidencePct}% Confidence</span>
                <Info size={11} className="text-[var(--color-text-muted)]" />
              </button>

              {showTooltip && (
                <div
                  className="absolute left-0 top-7 z-30 w-64 p-2.5 rounded-xl text-[11px] shadow-lg border animate-in fade-in duration-150"
                  style={{
                    backgroundColor: 'var(--color-surface)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <p className="font-semibold text-[var(--color-text-primary)] mb-1">
                    Calibrated Assessment:
                  </p>
                  <p>{vDetails.tooltip}</p>
                </div>
              )}
            </div>

            {/* Auditor review label if present */}
            {latestReviewAction && (
              <span className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-[var(--color-surface-subtle)] text-[var(--color-text-secondary)]">
                {latestReviewAction === 'confirmed' ? '✓ Verified by Auditor' : '✕ Dismissed'}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20 hover:bg-teal-500/20 transition-all cursor-pointer"
          >
            <span>{isExpanded ? 'Hide Source Evidence' : 'Show Source Evidence'}</span>
            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>

        {/* Semantic Reasoning Statement */}
        <p className="text-sm sm:text-base text-[var(--color-text-primary)] leading-relaxed font-medium">
          {reasoning}
        </p>
      </div>

      {/* Side-by-Side Evidence Comparison Area */}
      {isExpanded && (
        <div
          className="px-5 sm:px-6 pb-6 pt-3 space-y-4 border-t"
          style={{
            borderColor: 'var(--color-border-subtle)',
            backgroundColor: 'var(--color-surface-hover)',
          }}
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Side-by-Side Document Evidence
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Earlier Claim Card */}
            <div
              className="p-4 rounded-xl space-y-2 border"
              style={{
                backgroundColor: 'var(--color-earlier-quote-bg)',
                borderColor: 'var(--color-earlier-quote-border)',
              }}
            >
              <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                <span className="font-semibold text-[var(--color-text-secondary)]">Earlier Claim</span>
                <span className="font-mono text-[11px]">
                  {claimA.publishedAt ? new Date(claimA.publishedAt).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Initial Release'}
                </span>
              </div>
              <blockquote className="text-xs sm:text-sm text-[var(--color-text-primary)] leading-relaxed italic">
                "{claimA.excerpt}"
              </blockquote>
              <div className="pt-1">
                <a
                  href={claimA.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-[var(--color-accent)] hover:underline font-medium"
                >
                  <span>Official source link</span>
                  <ExternalLink size={11} />
                </a>
              </div>
            </div>

            {/* Later Claim Card */}
            <div
              className="p-4 rounded-xl space-y-2 border"
              style={{
                backgroundColor: 'var(--color-later-quote-bg)',
                borderColor: 'var(--color-later-quote-border)',
              }}
            >
              <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                <span className="font-semibold text-[var(--color-text-secondary)]">Later Claim</span>
                <span className="font-mono text-[11px]">
                  {claimB.publishedAt ? new Date(claimB.publishedAt).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Subsequent Release'}
                </span>
              </div>
              <blockquote className="text-xs sm:text-sm text-[var(--color-text-primary)] leading-relaxed italic">
                "{claimB.excerpt}"
              </blockquote>
              <div className="pt-1">
                <a
                  href={claimB.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-[var(--color-accent)] hover:underline font-medium"
                >
                  <span>Official source link</span>
                  <ExternalLink size={11} />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </article>
  );
};
