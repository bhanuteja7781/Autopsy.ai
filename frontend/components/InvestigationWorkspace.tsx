'use client';

import React, { useState } from 'react';
import { Search, Play, Plus, AlertTriangle, Filter, CheckCircle2, ShieldAlert, Sparkles, RefreshCw } from 'lucide-react';
import ClaimComparisonCard, { Verdict } from './ClaimComparisonCard';

interface Entity {
  id: string;
  name: string;
  canonical_slug: string;
  entity_type: string;
  comparison_count: number;
  contradiction_count: number;
  failure_count: number;
}

interface InvestigationWorkspaceProps {
  entities: Entity[];
  selectedEntity: Entity | null;
  onSelectEntity: (entity: Entity) => void;
  comparisons: any[];
  onTriggerInvestigation: (entityId: string) => void;
  onReviewComparison: (comparisonId: string, action: 'confirmed' | 'dismissed') => void;
  isInvestigating: boolean;
  onCreateEntity: (name: string, type: string) => void;
}

export const InvestigationWorkspace: React.FC<InvestigationWorkspaceProps> = ({
  entities,
  selectedEntity,
  onSelectEntity,
  comparisons,
  onTriggerInvestigation,
  onReviewComparison,
  isInvestigating,
  onCreateEntity,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'critical' | 'silent_contradiction' | 'explicit_update' | 'consistent'>('all');
  const [sortBy, setSortBy] = useState<'impact' | 'confidence' | 'verdict'>('impact');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newEntityName, setNewEntityName] = useState('');
  const [newEntityType, setNewEntityType] = useState('government_scheme');

  const filteredEntities = entities.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const criticalCount = comparisons.filter(
    (c) => (c.impactLevel || '').toUpperCase() === 'CRITICAL' || (c.impactScore || 0) >= 0.85
  ).length;
  const silentCount = comparisons.filter((c) => c.verdict === 'silent_contradiction').length;
  const updateCount = comparisons.filter((c) => c.verdict === 'explicit_update').length;
  const consistentCount = comparisons.filter((c) => c.verdict === 'consistent').length;

  const filteredComparisons = comparisons
    .filter((c) => {
      if (activeFilter === 'all') return true;
      if (activeFilter === 'critical') {
        return (c.impactLevel || '').toUpperCase() === 'CRITICAL' || (c.impactScore || 0) >= 0.85;
      }
      return c.verdict === activeFilter;
    })
    .sort((a, b) => {
      if (sortBy === 'impact') {
        const scoreA = a.priorityRank || (a.impactScore || 0.7);
        const scoreB = b.priorityRank || (b.impactScore || 0.7);
        return scoreB - scoreA;
      }
      if (sortBy === 'confidence') {
        return (b.confidence || 0) - (a.confidence || 0);
      }
      // Sort by verdict: silent contradictions first
      if (a.verdict === 'silent_contradiction' && b.verdict !== 'silent_contradiction') return -1;
      if (b.verdict === 'silent_contradiction' && a.verdict !== 'silent_contradiction') return 1;
      return (b.confidence || 0) - (a.confidence || 0);
    });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newEntityName.trim()) {
      onCreateEntity(newEntityName.trim(), newEntityType);
      setNewEntityName('');
      setIsModalOpen(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Column: Entity Sidebar */}
      <div className="lg:col-span-4 forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
            Tracked Entities ({entities.length})
          </h3>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-semibold hover:bg-cyan-500/30 transition-all cursor-pointer"
          >
            <Plus size={13} />
            <span>Track Entity</span>
          </button>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search schemes or policies..."
            className="w-full pl-8 pr-3 py-2 rounded-xl bg-[#080B12] border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-cyan-500 font-sans"
          />
        </div>

        {/* Entity List */}
        <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
          {filteredEntities.map((entity) => {
            const isSelected = selectedEntity?.id === entity.id;
            return (
              <button
                key={entity.id}
                onClick={() => onSelectEntity(entity)}
                className={`w-full p-3 rounded-xl border text-left transition-all flex items-center justify-between gap-2 cursor-pointer ${
                  isSelected
                    ? 'border-cyan-500/80 bg-[#131B2E] shadow-md'
                    : 'border-slate-800/80 bg-[#080B12]/60 hover:border-slate-700 hover:bg-[#0E1524]'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold text-slate-200 truncate">
                    {entity.name}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono capitalize">
                    {entity.entity_type.replace('_', ' ')}
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {entity.contradiction_count > 0 && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-red-950/80 text-red-300 border border-red-500/40 font-bold">
                      {entity.contradiction_count} drift
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right Column: Investigation Workspace Main Pane */}
      <div className="lg:col-span-8 space-y-4">
        {selectedEntity ? (
          <div className="space-y-4">
            {/* Entity Header Banner */}
            <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-5 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-100">
                    {selectedEntity.name}
                  </h2>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {selectedEntity.entity_type.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Tracking public notices, guidelines, and gazettes prioritized by real-world policy impact.
                </p>
              </div>

              <button
                onClick={() => onTriggerInvestigation(selectedEntity.id)}
                disabled={isInvestigating}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-black font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 disabled:opacity-50 cursor-pointer"
              >
                <Play className={`w-3.5 h-3.5 fill-current ${isInvestigating ? 'animate-spin' : ''}`} />
                <span>{isInvestigating ? 'Auditing Policy...' : 'Run Investigation'}</span>
              </button>
            </div>

            {/* Filter & Sort Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2 text-xs">
              <div className="flex flex-wrap items-center gap-1.5 bg-[#0B0F19] p-1 rounded-xl border border-slate-800">
                <button
                  onClick={() => setActiveFilter('all')}
                  className={`px-3 py-1 rounded-lg font-medium transition-all ${
                    activeFilter === 'all' ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  All ({comparisons.length})
                </button>
                {criticalCount > 0 && (
                  <button
                    onClick={() => setActiveFilter('critical')}
                    className={`px-3 py-1 rounded-lg font-medium transition-all ${
                      activeFilter === 'critical' ? 'bg-rose-600 text-white font-semibold' : 'text-rose-400 hover:text-rose-200'
                    }`}
                  >
                    Critical Impact ({criticalCount})
                  </button>
                )}
                <button
                  onClick={() => setActiveFilter('silent_contradiction')}
                  className={`px-3 py-1 rounded-lg font-medium transition-all ${
                    activeFilter === 'silent_contradiction' ? 'bg-red-500 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Silent Reversals ({silentCount})
                </button>
                <button
                  onClick={() => setActiveFilter('explicit_update')}
                  className={`px-3 py-1 rounded-lg font-medium transition-all ${
                    activeFilter === 'explicit_update' ? 'bg-blue-500 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Explicit Updates ({updateCount})
                </button>
                <button
                  onClick={() => setActiveFilter('consistent')}
                  className={`px-3 py-1 rounded-lg font-medium transition-all ${
                    activeFilter === 'consistent' ? 'bg-slate-700 text-slate-200 font-semibold' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Consistent ({consistentCount})
                </button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Sort:</span>
                <select
                  value={sortBy}
                  onChange={(e: any) => setSortBy(e.target.value)}
                  className="bg-[#080B12] border border-slate-800 rounded-lg px-2 py-1 text-slate-300 text-[11px] font-mono focus:outline-none focus:border-cyan-500"
                >
                  <option value="impact">Highest Policy Impact</option>
                  <option value="confidence">Confidence Score</option>
                  <option value="verdict">Contradiction Type</option>
                </select>
              </div>
            </div>

            {/* Comparisons List with ClaimComparisonCard */}
            {filteredComparisons.length === 0 ? (
              <div className="forensic-glass-card rounded-2xl p-12 text-center text-slate-400 space-y-3 border border-slate-800 bg-[#0B0F19]">
                <ShieldAlert className="w-8 h-8 mx-auto text-slate-500" />
                <div className="text-sm font-semibold text-slate-200">No Comparisons Recorded Yet</div>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Click "Run Investigation" to trigger live retrieval and pairwise drift classification.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredComparisons.map((comp) => (
                  <ClaimComparisonCard
                    key={comp.comparisonId}
                    comparisonId={comp.comparisonId}
                    verdict={comp.verdict as Verdict}
                    confidence={comp.confidence}
                    reasoning={comp.reasoning}
                    claimA={comp.claimA}
                    claimB={comp.claimB}
                    impactLevel={comp.impactLevel}
                    impactScore={comp.impactScore}
                    impactCategory={comp.impactCategory}
                    impactSummary={comp.impactSummary}
                    onReview={onReviewComparison}
                    latestReviewAction={comp.latestReviewAction}
                  />
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="forensic-glass-card rounded-2xl p-16 text-center text-slate-400 space-y-3 border border-slate-800 bg-[#0B0F19]">
            <Search className="w-8 h-8 mx-auto text-slate-600" />
            <div className="text-sm font-semibold text-slate-200">Select an Entity to Investigate</div>
            <p className="text-xs text-slate-400 max-w-xs mx-auto">
              Choose a scheme or policy from the left panel to inspect pairwise drift verdicts.
            </p>
          </div>
        )}
      </div>

      {/* Track Entity Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl animate-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-slate-100">
              Track New Policy or Entity
            </h3>
            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Entity / Scheme Name:</label>
                <input
                  type="text"
                  required
                  value={newEntityName}
                  onChange={(e) => setNewEntityName(e.target.value)}
                  placeholder="e.g. PM Street Vendor's AtmaNirbhar Nidhi"
                  className="w-full p-2.5 rounded-xl bg-[#080B12] border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Entity Category:</label>
                <select
                  value={newEntityType}
                  onChange={(e) => setNewEntityType(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-[#080B12] border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                >
                  <option value="government_scheme">Government Scheme</option>
                  <option value="corporate_policy">Corporate ToS / Policy</option>
                  <option value="software_changelog">Software Changelog</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-slate-200 bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-cyan-400 text-black font-semibold hover:bg-cyan-300"
                >
                  Save &amp; Track
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
