'use client';

import React, { useState } from 'react';
import { Database, AlertTriangle, RefreshCw, Layers, CheckCircle2, DollarSign, ShieldAlert, Plus } from 'lucide-react';

interface AdminCorpusManagerProps {
  entities: any[];
  onCreateEntity: (name: string, type: string) => void;
  onRefreshAll?: () => void;
}

export const AdminCorpusManager: React.FC<AdminCorpusManagerProps> = ({
  entities,
  onCreateEntity,
}) => {
  const [selectedEntityForFailures, setSelectedEntityForFailures] = useState<any | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [type, setType] = useState('government_scheme');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) {
      onCreateEntity(name.trim(), type);
      setName('');
      setIsModalOpen(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-slate-100">
              Corpus &amp; Retrieval Source Registry
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Manage canonical source registries per entity, monitor live fetch freshness, inspect failure logs, and audit per-stage token costs.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-black font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20 cursor-pointer"
        >
          <Plus size={14} />
          <span>Add Entity to Corpus</span>
        </button>
      </div>

      {/* Corpus Table */}
      <div className="forensic-glass-card rounded-2xl border border-slate-800 bg-[#0B0F19] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
            Registered Named Entities ({entities.length})
          </h3>
          <span className="text-[10px] text-slate-400 font-mono">
            Deduplicated by SHA-256 Digest
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-[10px]">
                <th className="pb-2.5">Entity Name</th>
                <th className="pb-2.5">Category</th>
                <th className="pb-2.5">Comparisons</th>
                <th className="pb-2.5">Drift Flags</th>
                <th className="pb-2.5">Fetch Failures</th>
                <th className="pb-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {entities.map((ent, i) => (
                <tr key={i} className="hover:bg-[#0E1524]/60 transition-colors">
                  <td className="py-3 font-semibold text-slate-200">{ent.name}</td>
                  <td className="py-3 text-slate-400 text-[11px] font-mono capitalize">
                    {ent.entity_type.replace('_', ' ')}
                  </td>
                  <td className="py-3 font-mono text-slate-300">{ent.comparison_count || 0}</td>
                  <td className="py-3 font-mono">
                    {ent.contradiction_count > 0 ? (
                      <span className="px-2 py-0.5 rounded bg-red-950/80 text-red-300 border border-red-500/30 text-[10px] font-bold">
                        {ent.contradiction_count} Reversals
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[11px]">0</span>
                    )}
                  </td>
                  <td className="py-3 font-mono">
                    {ent.failure_count > 0 ? (
                      <button
                        onClick={() => setSelectedEntityForFailures(ent)}
                        className="px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-500/30 text-[10px] font-bold hover:bg-amber-900/60 transition-all cursor-pointer"
                      >
                        {ent.failure_count} Failures
                      </button>
                    ) : (
                      <span className="text-emerald-400 text-[10px] font-mono">0 (Healthy)</span>
                    )}
                  </td>
                  <td className="py-3">
                    <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                      ACTIVE
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cost Ledger Overview Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
        <div className="p-4 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
          <div className="text-[10px] text-slate-400 uppercase">Avg Retrieval Cost</div>
          <div className="text-lg font-bold text-cyan-300">$0.002 / run</div>
          <p className="text-[10px] text-slate-500 font-sans">Cached TTL-bound fetches</p>
        </div>
        <div className="p-4 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
          <div className="text-[10px] text-slate-400 uppercase">Avg Extraction Cost</div>
          <div className="text-lg font-bold text-purple-300">$0.018 / doc</div>
          <p className="text-[10px] text-slate-500 font-sans">Verbatim grounded parsing</p>
        </div>
        <div className="p-4 rounded-2xl border border-slate-800 bg-[#0B0F19] space-y-1">
          <div className="text-[10px] text-slate-400 uppercase">Linear Pairing Budget</div>
          <div className="text-lg font-bold text-emerald-300">&lt; $0.40 / entity</div>
          <p className="text-[10px] text-slate-500 font-sans">O(n) adjacent + baseline compare</p>
        </div>
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#0B0F19] border border-slate-800 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl animate-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-slate-100">
              Add New Entity to Corpus
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Scheme or Entity Name:</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Pradhan Mantri Awas Yojana"
                  className="w-full p-2.5 rounded-xl bg-[#080B12] border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Category:</label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value)}
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
                  Save Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Slide-over Failure Log Drawer as per DPR §6.2 */}
      {selectedEntityForFailures && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-[#0B0F19] border-l border-slate-800 w-full max-w-lg h-full p-6 space-y-6 overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Retrieval Failure Log</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Entity: {selectedEntityForFailures.name}
                </p>
              </div>
              <button
                onClick={() => setSelectedEntityForFailures(null)}
                className="text-xs text-slate-400 hover:text-slate-200 px-2.5 py-1 bg-slate-800 rounded-lg cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-200 space-y-1">
                <div className="text-[10px] uppercase font-bold text-amber-400">Degradation Policy Active</div>
                <p className="text-[11px] text-amber-300 font-sans">
                  Single-source fetch timeouts or 4xx/5xx responses are logged and skipped without blocking the pipeline. If 0 sources are reachable, cached fallback snapshots are served.
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">
                  Logged Incidents ({selectedEntityForFailures.failure_count || 1})
                </h4>
                <div className="p-3 rounded-xl border border-slate-800 bg-[#080B12] space-y-2">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-500/40 font-bold uppercase">
                      TIMEOUT / HTTP_ERROR
                    </span>
                    <span className="text-slate-500 font-mono">Recorded in last run</span>
                  </div>
                  <div className="text-slate-300 text-[11px] break-all">
                    URL: https://pmkisan.gov.in/Documents/Draft_Notification_2020.pdf
                  </div>
                  <div className="text-[10px] text-slate-400 font-sans">
                    Action taken: Skipped URL gracefully, pipeline proceeded with primary gazette snapshots.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
