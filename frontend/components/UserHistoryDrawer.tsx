'use client';

import React, { useState, useEffect } from 'react';
import { History, X, Clock, AlertTriangle, CheckCircle, Trash2, ArrowRight, Sparkles } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8008';

export interface HistoryItem {
  id: string;
  entity_id: string;
  entity_name: string;
  contradiction_count: number;
  comparison_count: number;
  searched_at: string;
}

interface UserHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPolicy: (entityId: string, entityName: string) => void;
}

export function UserHistoryDrawer({ isOpen, onClose, onSelectPolicy }: UserHistoryDrawerProps) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = async () => {
    const savedUser = localStorage.getItem('autopsy_user');
    if (!savedUser) return;
    try {
      const user = JSON.parse(savedUser);
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/api/users/${user.id}/history`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.error('Failed to load user history:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen]);

  const handleDelete = async (historyId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const savedUser = localStorage.getItem('autopsy_user');
    if (!savedUser) return;
    try {
      const user = JSON.parse(savedUser);
      await fetch(`${API_BASE}/api/users/${user.id}/history/${historyId}`, { method: 'DELETE' });
      setHistory((prev) => prev.filter((item) => item.id !== historyId));
    } catch (e) {
      console.error(e);
    }
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      if (diffMins < 2) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
      {/* Click outside to close */}
      <div className="flex-1" onClick={onClose} />

      {/* Drawer Body */}
      <div className="w-full max-w-md bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl h-full flex flex-col animate-in slide-in-from-right duration-250">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-600 dark:text-teal-400">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">Audit History</h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Your recent searches &amp; forensic results
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {isLoading ? (
            <div className="py-12 text-center text-xs text-slate-400">
              <Clock className="w-5 h-5 mx-auto mb-2 animate-spin text-teal-500" />
              <span>Loading your previous policy audits...</span>
            </div>
          ) : history.length === 0 ? (
            <div className="py-16 text-center px-4">
              <History className="w-10 h-10 mx-auto mb-3 text-slate-300 dark:text-slate-700" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No searches yet</p>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 max-w-xs mx-auto">
                Search any Indian policy, statute, or government scheme to automatically save your audit trail.
              </p>
            </div>
          ) : (
            history.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  onSelectPolicy(item.entity_id, item.entity_name);
                  onClose();
                }}
                className="group relative p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/60 hover:border-teal-500/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all cursor-pointer shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-xs font-bold text-slate-900 dark:text-white truncate group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors">
                      {item.entity_name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1.5 text-[10px]">
                      {item.contradiction_count > 0 ? (
                        <span className="inline-flex items-center gap-1 font-semibold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/50 px-2 py-0.5 rounded-md border border-rose-200 dark:border-rose-900/50">
                          <AlertTriangle className="w-3 h-3" />
                          <span>{item.contradiction_count} Silent Shift{item.contradiction_count !== 1 ? 's' : ''}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-0.5 rounded-md border border-emerald-200 dark:border-emerald-900/50">
                          <CheckCircle className="w-3 h-3" />
                          <span>Verified Consistent</span>
                        </span>
                      )}
                      <span className="text-slate-400 font-mono">· {formatTime(item.searched_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => handleDelete(item.id, e)}
                      title="Delete from history"
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-all cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-teal-500 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 text-center text-[11px] text-slate-400 font-mono">
          <span>Click any policy to immediately view cached forensic findings</span>
        </div>
      </div>
    </div>
  );
}
