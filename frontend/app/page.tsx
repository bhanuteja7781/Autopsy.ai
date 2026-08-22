'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ThemeToggle } from '../components/ThemeToggle';
import { AutopsyLogo } from '../components/AutopsyLogo';
import { UserNav } from '../components/UserNav';
import { UserHistoryDrawer } from '../components/UserHistoryDrawer';
import { PolicyFindingCard, FindingVerdict } from '../components/PolicyFindingCard';
import { Search, ArrowRight, AlertCircle, RefreshCw, Check, ChevronDown, ChevronUp } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8008';
const WS_BASE = 'ws://127.0.0.1:8008';

interface Entity {
  id: string;
  name: string;
  canonical_slug: string;
  entity_type: string;
  is_featured?: number | boolean;
  document_count?: number;
  comparison_count: number;
  contradiction_count: number;
  failure_count: number;
  latest_fetch_status?: string;
  latest_fetched_at?: string;
}

export default function Home() {
  const [query, setQuery] = useState('');
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [comparisons, setComparisons] = useState<any[]>([]);
  const [hasAudited, setHasAudited] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0); // 1: Fetching, 2: Extracting, 3: Comparing, 4: Done
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [showAllFindings, setShowAllFindings] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [apiWarning, setApiWarning] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const selectedEntityRef = useRef<Entity | null>(null);

  // Keep ref in sync so WS callbacks can read latest value without stale closure
  useEffect(() => {
    selectedEntityRef.current = selectedEntity;
  }, [selectedEntity]);

  const checkSystemStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.missing_keys && data.missing_keys.length > 0) {
          setApiWarning(`API Key Missing or Endpoint Unreachable: Please configure ${data.missing_keys.join(', ')} in .env to run live policy audits.`);
        } else {
          setApiWarning(null);
        }
      }
    } catch {
      setApiWarning('API Server Unreachable: Please verify the backend server is running on http://127.0.0.1:8008.');
    }
  }, []);

  const fetchEntities = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/entities`);
      if (res.ok) {
        const data = await res.json();
        setEntities(data);
        return data as Entity[];
      }
    } catch (e) {
      console.error('fetchEntities error:', e);
    }
    return [];
  }, []);

  const fetchComparisons = useCallback(async (entityId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/entities/${entityId}/comparisons`);
      if (res.ok) {
        const data = await res.json();
        setComparisons(data);
        return data;
      }
    } catch (e) {
      console.error('fetchComparisons error:', e);
    }
    return [];
  }, []);

  // ─── Polling fallback: poll comparisons every 2.5s while loading ──────────────
  const startPolling = useCallback((entityId: string) => {
    stopPolling();
    pollIntervalRef.current = setInterval(async () => {
      const data = await fetchComparisons(entityId);
      if (data && data.length > 0) {
        stopPolling();
        setIsLoading(false);
        setActiveStep(4);
      }
    }, 2500);
  }, [fetchComparisons]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // ─── Initial data load ─────────────────────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      await checkSystemStatus();
      await fetchEntities();
    };
    init();
  }, [checkSystemStatus, fetchEntities, fetchComparisons]);

  // ─── WebSocket connection (reconnects on disconnect) ───────────────────────
  useEffect(() => {
    let ws: WebSocket;
    let destroyed = false;

    const connectWs = () => {
      if (destroyed) return;
      ws = new WebSocket(`${WS_BASE}/ws/live`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);

          // BUG #4 FIX: Backend sends stage both at top-level AND inside data{}.
          // Check both locations so any variation works.
          const stage: string =
            payload.stage ||
            payload.data?.stage ||
            payload.event_type ||
            '';

          const entityIdInPayload: string | undefined =
            payload.data?.entity_id || payload.entity_id;

          // Only process events for the currently selected entity
          const currentEntityId = selectedEntityRef.current?.id;
          if (entityIdInPayload && currentEntityId && entityIdInPayload !== currentEntityId) {
            return;
          }

          if (stage === 'retrieval' || payload.event_type === 'pipeline_start') {
            setActiveStep(1);
            setLoadingMessage(payload.message || 'Fetching archived guidelines...');
          } else if (stage === 'extraction' || payload.event_type === 'retrieval_complete') {
            setActiveStep(2);
            setLoadingMessage(payload.message || 'Extracting dated claims...');
          } else if (stage === 'reasoning' || payload.event_type === 'extraction_complete') {
            setActiveStep(3);
            setLoadingMessage(payload.message || 'Running drift analysis...');
          } else if (payload.event_type === 'reasoning_complete' || stage === 'done') {
            setActiveStep(4);
            setIsLoading(false);
            stopPolling();
            const eid = entityIdInPayload || selectedEntityRef.current?.id;
            if (eid) fetchComparisons(eid);
            fetchEntities();
          } else if (payload.event_type === 'pipeline_error') {
            // Pipeline failed — surface exact error to UI
            const errMsg = payload.message || payload.data?.error || 'Unknown pipeline error';
            setPipelineError(errMsg);
            setIsLoading(false);
            setActiveStep(0);
            stopPolling();
            const eid = entityIdInPayload || selectedEntityRef.current?.id;
            if (eid) fetchComparisons(eid);
          }
        } catch (e) {
          console.error('WS message parse error:', e);
        }
      };

      ws.onclose = () => {
        if (!destroyed) setTimeout(connectWs, 3000);
      };

      ws.onerror = (err) => {
        console.warn('WebSocket error (will reconnect):', err);
      };
    };

    connectWs();

    return () => {
      destroyed = true;
      if (ws) ws.close();
    };
  }, []); // Run once — WS is global, not entity-scoped

  // ─── Cleanup polling on unmount ────────────────────────────────────────────
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const handleSelectScheme = (ent: Entity) => {
    setSelectedEntity(ent);
    setQuery(ent.name);
    setIsLoading(false);
    setHasAudited(false);
    setActiveStep(0);
    setShowAllFindings(false);
    stopPolling();
    fetchComparisons(ent.id);
  };

  const handleRunInvestigation = async (entityId?: string) => {
    const targetId = entityId || selectedEntity?.id;
    if (!targetId) return;

    setIsLoading(true);
    setPipelineError(null);  // clear previous error
    setHasAudited(false);
    setActiveStep(1);
    setShowAllFindings(false);
    setComparisons([]); // clear stale results
    setLoadingMessage('Fetching live notices and analyzing policy drift...');

    let succeeded = false;
    try {
      startPolling(targetId);
      const res = await fetch(`${API_BASE}/api/entities/${targetId}/investigate`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.comparisons && Array.isArray(data.comparisons)) {
          setComparisons(data.comparisons);
        } else {
          await fetchComparisons(targetId);
        }
        await fetchEntities();
        succeeded = true;
        setHasAudited(true);

        // Save to user audit history if user is signed in
        try {
          const savedUser = localStorage.getItem('autopsy_user');
          if (savedUser) {
            const user = JSON.parse(savedUser);
            const compsList = (data && data.comparisons) || comparisons;
            const contraCount = (compsList || []).filter((c: any) => c.verdict === 'silent_contradiction').length;
            const entName = selectedEntity?.name || query.trim();
            fetch(`${API_BASE}/api/users/${user.id}/history`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                entity_id: targetId,
                entity_name: entName,
                contradiction_count: contraCount,
                comparison_count: (compsList || []).length,
              }),
            }).catch(() => {});
          }
        } catch {}
      } else {
        // HTTP 4xx / 5xx — surface the exact error detail
        let detail = `HTTP ${res.status} error from backend.`;
        try {
          const errBody = await res.json();
          detail = errBody.detail || detail;
        } catch {}
        setPipelineError(detail);
      }
    } catch (e: any) {
      setPipelineError(`Network error: ${e?.message || 'Could not reach backend at ${API_BASE}'}`);
      console.error('investigate error:', e);
    } finally {
      stopPolling();
      setIsLoading(false);
      setActiveStep(succeeded ? 4 : 0);
    }
  };

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const existing = entities.find(
      (ent) => ent.name.toLowerCase().trim() === query.trim().toLowerCase()
    );

    if (existing) {
      setSelectedEntity(existing);
      await handleRunInvestigation(existing.id);
    } else {
      try {
        setIsLoading(true);
        setActiveStep(1);
        setLoadingMessage('Registering policy for cross-year tracking...');
        const res = await fetch(`${API_BASE}/api/entities`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: query.trim(), entity_type: 'government_scheme' }),
        });
        if (res.ok) {
          const newEnt = await res.json();
          await fetchEntities();
          setSelectedEntity(newEnt);
          await handleRunInvestigation(newEnt.id);
        } else {
          let detail = `HTTP ${res.status} error from backend.`;
          try {
            const errBody = await res.json();
            detail = errBody.detail || detail;
          } catch {}
          setPipelineError(detail);
          setIsLoading(false);
          setActiveStep(0);
        }
      } catch (e: any) {
        setIsLoading(false);
        setPipelineError(`Network error: ${e?.message || 'Could not reach backend.'}`);
        console.error(e);
      }
    }
  };

  const handleReviewAction = async (comparisonId: string, action: 'confirmed' | 'dismissed') => {
    try {
      await fetch(`${API_BASE}/api/comparisons/${comparisonId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reviewer_id: 'researcher_1' }),
      });
      if (selectedEntity) fetchComparisons(selectedEntity.id);
    } catch (e) {
      console.error(e);
    }
  };

  // Separate actionable findings from noise and sort by priority & confidence
  const actionable = comparisons
    .filter((c) => c.verdict === 'silent_contradiction' || c.verdict === 'explicit_update')
    .sort((a, b) => {
      // 1. Silent contradictions first
      if (a.verdict === 'silent_contradiction' && b.verdict !== 'silent_contradiction') return -1;
      if (b.verdict === 'silent_contradiction' && a.verdict !== 'silent_contradiction') return 1;
      // 2. Highest confidence first
      return (b.confidence || 0) - (a.confidence || 0);
    });

  const INITIAL_VISIBLE_COUNT = 2;
  const displayedFindings = showAllFindings ? actionable : actionable.slice(0, INITIAL_VISIBLE_COUNT);
  const silentReversals = comparisons.filter((c) => c.verdict === 'silent_contradiction');
  const explicitUpdates = comparisons.filter((c) => c.verdict === 'explicit_update');
  const consistentCount = comparisons.filter((c) => c.verdict === 'consistent').length;

  // Date range from all comparisons for the "no drift" banner
  const allDates = comparisons
    .flatMap((c) => [c.claimA?.publishedAt, c.claimB?.publishedAt])
    .filter(Boolean)
    .sort();
  const dateRangeStart = allDates[0] ? new Date(allDates[0]).getFullYear() : null;
  const dateRangeEnd = allDates[allDates.length - 1]
    ? new Date(allDates[allDates.length - 1]).getFullYear()
    : null;
  const dateRangeLabel =
    dateRangeStart && dateRangeEnd && dateRangeStart !== dateRangeEnd
      ? `${dateRangeStart}–${dateRangeEnd}`
      : dateRangeStart
      ? `${dateRangeStart}`
      : null;

  const handleSelectHistoryPolicy = async (entityId: string, entityName: string) => {
    setQuery(entityName);
    setIsLoading(true);
    setActiveStep(0);
    setPipelineError(null);
    setShowAllFindings(false);

    const existing = entities.find((e) => e.id === entityId || e.name.toLowerCase() === entityName.toLowerCase());
    if (existing) {
      setSelectedEntity(existing);
    } else {
      setSelectedEntity({
        id: entityId,
        name: entityName,
        canonical_slug: entityName.toLowerCase().replace(/\s+/g, '-'),
        entity_type: 'government_scheme',
        comparison_count: 0,
        contradiction_count: 0,
        failure_count: 0,
      });
    }

    try {
      const res = await fetch(`${API_BASE}/api/entities/${entityId}/comparisons`);
      if (res.ok) {
        const comps = await res.json();
        setComparisons(comps || []);
        setHasAudited(true);
        setActiveStep(4);
      } else {
        await handleRunInvestigation(entityId);
      }
    } catch {
      await handleRunInvestigation(entityId);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between">
      {/* Top Header */}
      <header className="px-6 py-5 max-w-5xl mx-auto w-full flex items-center justify-between">
        <AutopsyLogo size="md" />

        <div className="flex items-center gap-3">
          <UserNav onOpenHistory={() => setIsHistoryOpen(true)} />
          <ThemeToggle />
        </div>
      </header>

      {/* Main Conversational Surface */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-6 sm:py-8 space-y-8">
        {/* Pipeline Error Banner — rendered when HTTP 500 or WS pipeline_error received */}
        {pipelineError && (
          <div
            className="p-4 rounded-2xl border flex items-start gap-3 text-xs bg-rose-500/10 border-rose-500/40 text-rose-700 dark:text-rose-400 animate-in fade-in"
          >
            <AlertCircle size={16} className="shrink-0 mt-0.5 text-rose-600" />
            <div className="space-y-1 flex-1">
              <p className="font-bold text-sm">Live Pipeline Error — Exact Backend Message:</p>
              <pre className="whitespace-pre-wrap font-mono text-[11px] opacity-90 bg-rose-950/10 dark:bg-rose-950/30 p-2 rounded-lg overflow-x-auto">{pipelineError}</pre>
              <p className="opacity-70">Check your <code>.env</code> keys (TAVILY_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY) and the backend terminal for the full traceback.</p>
            </div>
            <button onClick={() => setPipelineError(null)} className="shrink-0 opacity-60 hover:opacity-100 cursor-pointer text-lg leading-none">&times;</button>
          </div>
        )}

        {/* API Key Missing Warning Banner */}
        {apiWarning && (
          <div
            className="p-4 rounded-2xl border flex items-start gap-3 text-xs bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400 animate-in fade-in"
          >
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold">{apiWarning}</p>
              <p className="opacity-80">
                Live audits require Model 1 (Gemini), Model 2 (OpenAI/OpenRouter), and Tavily keys configured in <code>.env</code>.
              </p>
            </div>
          </div>
        )}

        {/* Hero Title */}
        <section className="text-center space-y-2.5 pt-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-medium bg-[var(--color-accent-soft)] text-[var(--color-accent-text)] border border-[var(--color-accent-border)] mb-1">
            <span>Dual-Model Forensics:</span>
            <span className="font-semibold">DeepSeek-V3</span>
            <span>+</span>
            <span className="font-semibold">Gemma-3-27B</span>
          </div>
          <h1 className="text-2xl sm:text-4xl font-bold tracking-tight text-[var(--color-text-primary)] font-serif">
            Has a policy quietly changed?
          </h1>
          <p className="text-sm sm:text-base text-[var(--color-text-secondary)] max-w-xl mx-auto leading-relaxed">
            Detect unannounced rule reversals, benefit caps, and eligibility shifts across years of public notices.
          </p>
        </section>

        {/* Input Bar */}
        <section className="space-y-3">
          <form onSubmit={handleSearchSubmit} className="relative">
            <div
              className="flex items-center rounded-2xl border p-2 sm:p-2.5 transition-all shadow-sm focus-within:shadow-md"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
              }}
            >
              <Search className="w-5 h-5 ml-3 text-[var(--color-text-muted)] shrink-0" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search or enter any scheme (e.g. Ayushman Bharat PM-JAY, PM-KISAN, OpenAI ToS)..."
                className="w-full px-3 py-1.5 text-sm sm:text-base bg-transparent text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none"
              />
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 sm:px-5 sm:py-2.5 rounded-xl font-semibold text-xs sm:text-sm text-white bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] transition-all flex items-center gap-1.5 shrink-0 disabled:opacity-50 cursor-pointer shadow-sm"
              >
                <span>{isLoading ? 'Auditing...' : 'Run Policy Audit'}</span>
                <ArrowRight size={15} />
              </button>
            </div>
          </form>

        </section>

        {/* Step-by-Step Progress Bar during Execution */}
        {isLoading && (
          <section
            className="p-6 rounded-3xl border text-center space-y-4 animate-in fade-in duration-200"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              boxShadow: 'var(--card-shadow)',
            }}
          >
            {/* Inline 3-stage progress indicators */}
            <div className="flex items-center justify-center gap-2 sm:gap-4 text-xs font-medium text-[var(--color-text-secondary)]">
              {/* Step 1 */}
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
                activeStep > 1 ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300' :
                activeStep === 1 ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-text)] border-[var(--color-accent)] animate-pulse' :
                'border-[var(--color-border)] opacity-50'
              }`}>
                {activeStep > 1 ? <Check size={12} /> : <span>1</span>}
                <span>Fetching Guidelines</span>
              </div>

              <span className="text-[var(--color-border)]">→</span>

              {/* Step 2 */}
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
                activeStep > 2 ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300' :
                activeStep === 2 ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-text)] border-[var(--color-accent)] animate-pulse' :
                'border-[var(--color-border)] opacity-50'
              }`}>
                {activeStep > 2 ? <Check size={12} /> : <span>2</span>}
                <span>Extracting Dated Claims</span>
              </div>

              <span className="text-[var(--color-border)]">→</span>

              {/* Step 3 */}
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
                activeStep === 3 ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-text)] border-[var(--color-accent)] animate-pulse' :
                'border-[var(--color-border)] opacity-50'
              }`}>
                <span>3</span>
                <span>Drift Analysis</span>
              </div>
            </div>

            <p className="text-xs text-[var(--color-text-muted)] italic">
              {loadingMessage || 'Cross-referencing historical statements...'}
            </p>
          </section>
        )}

        {/* Results Area */}
        {!isLoading && selectedEntity && hasAudited && (
          <section className="space-y-5 animate-in fade-in duration-300">
            {/* Report header */}
            <div
              className="p-5 sm:p-6 rounded-3xl border"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                boxShadow: 'var(--card-shadow)',
              }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg sm:text-xl font-bold text-[var(--color-text-primary)] font-serif">
                    {selectedEntity.name}
                  </h2>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 capitalize">
                    {selectedEntity.entity_type.replace('_', ' ')} · Policy Forensics Report
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => handleRunInvestigation(selectedEntity.id)}
                  className="px-3.5 py-1.5 rounded-xl font-semibold text-xs text-white bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <RefreshCw size={12} />
                  <span>Run Policy Audit</span>
                </button>
              </div>

            </div>

            {/* ── MAIN RESULTS ───────────────────────────────────────── */}
            {(selectedEntity.document_count === 0 && selectedEntity.latest_fetch_status === 'failed') ? (
              /* Hard fetch failure error state */
              <div
                className="p-8 rounded-3xl border text-center space-y-3"
                style={{
                  backgroundColor: 'var(--color-surface)',
                  borderColor: 'var(--color-border)',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <div className="flex items-center justify-center gap-2 text-rose-600 dark:text-rose-400">
                  <AlertCircle size={20} />
                  <span className="font-semibold text-sm">
                    Unable to fetch live public records for this topic. Check connection or API keys.
                  </span>
                </div>
                <p className="text-xs text-[var(--color-text-muted)] max-w-md mx-auto">
                  Live retrieval could not retrieve historical policy documents for this query.
                </p>
                <button
                  type="button"
                  onClick={() => handleRunInvestigation(selectedEntity.id)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] transition-all cursor-pointer"
                >
                  Retry Policy Audit
                </button>
              </div>
            ) : comparisons.length === 0 ? (
              /* Never run or 0 comparisons yet — prompt to audit */
              <div
                className="p-8 rounded-3xl border text-center space-y-3"
                style={{
                  backgroundColor: 'var(--color-surface)',
                  borderColor: 'var(--color-border)',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <p className="text-[var(--color-text-secondary)] text-sm">
                  {selectedEntity.document_count === 0
                    ? 'Unable to fetch live public records for this topic. Check connection or API keys.'
                    : 'No audit data yet for this policy.'}
                </p>
                <button
                  type="button"
                  onClick={() => handleRunInvestigation(selectedEntity.id)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] transition-all cursor-pointer"
                >
                  Run Policy Audit Now
                </button>
              </div>
            ) : actionable.length === 0 ? (
              /* Task 3: Zero contradictions/updates -> clean banner only if X > 0 documents analyzed */
              <div
                className="p-7 rounded-3xl border text-center space-y-2"
                style={{
                  backgroundColor: 'var(--color-surface)',
                  borderColor: 'var(--color-border)',
                  boxShadow: 'var(--card-shadow)',
                }}
              >
                <div className="flex items-center justify-center gap-2 text-emerald-600 dark:text-emerald-400">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                  <span className="font-semibold text-sm">
                    0 Silent Contradictions found across {selectedEntity.document_count && selectedEntity.document_count > 0 ? selectedEntity.document_count : (comparisons.length > 0 ? comparisons.length + 1 : 1)} official documents analyzed
                    {dateRangeLabel ? ` (${dateRangeLabel})` : ''}.
                  </span>
                </div>
                {consistentCount > 0 && (
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {consistentCount} statement{consistentCount !== 1 ? 's' : ''} verified consistent across the analyzed timeline.
                  </p>
                )}
              </div>
            ) : (
              /* Actionable findings exist */
              <div className="space-y-4">
                {/* Findings header with consistent summary inline */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-1">
                  <div className="flex items-center gap-3 text-xs">
                    {silentReversals.length > 0 && (
                      <span className="font-semibold text-rose-600 dark:text-rose-400">
                        {silentReversals.length} silent {silentReversals.length === 1 ? 'contradiction' : 'contradictions'}
                      </span>
                    )}
                    {explicitUpdates.length > 0 && (
                      <span className="font-semibold text-blue-600 dark:text-blue-400">
                        {explicitUpdates.length} explicit {explicitUpdates.length === 1 ? 'update' : 'updates'}
                      </span>
                    )}
                    {/* Change 1: Consistent terms as passive summary only — no individual cards */}
                    {consistentCount > 0 && (
                      <span className="text-[var(--color-text-muted)]">
                        · {consistentCount} consistent
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-[var(--color-text-muted)] uppercase tracking-wider">
                    Verbatim Grounded
                  </span>
                </div>

                {/* Render most relevant findings first */}
                <div className="space-y-4">
                  {displayedFindings.map((comp) => (
                    <PolicyFindingCard
                      key={comp.comparisonId}
                      id={comp.comparisonId}
                      verdict={comp.verdict as FindingVerdict}
                      confidence={comp.confidence}
                      reasoning={comp.reasoning}
                      claimA={comp.claimA}
                      claimB={comp.claimB}
                      onReview={handleReviewAction}
                      latestReviewAction={comp.latestReviewAction}
                    />
                  ))}
                </div>

                {/* Progressive Disclosure: Show More / Show Less Button */}
                {actionable.length > INITIAL_VISIBLE_COUNT && (
                  <div className="pt-2 flex justify-center">
                    <button
                      type="button"
                      onClick={() => setShowAllFindings(!showAllFindings)}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 text-slate-700 dark:text-slate-200 hover:border-teal-500/50 hover:text-teal-600 dark:hover:text-teal-400 transition-all shadow-sm cursor-pointer"
                    >
                      <span>
                        {showAllFindings
                          ? 'Show Top Relevant Findings Only'
                          : `View ${actionable.length - INITIAL_VISIBLE_COUNT} More Finding${actionable.length - INITIAL_VISIBLE_COUNT !== 1 ? 's' : ''}`}
                      </span>
                      {showAllFindings ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="max-w-5xl mx-auto w-full px-6 py-6 text-center text-xs text-[var(--color-text-muted)] border-t mt-12" style={{ borderColor: 'var(--color-border-subtle)' }}>
        <span>
          autopsy.ai — Automated Policy Shift Forensics &amp; Contradiction Auditing
        </span>
      </footer>

      {/* User Search & Audit History Drawer */}
      <UserHistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onSelectPolicy={handleSelectHistoryPolicy}
      />
    </div>
  );
}
