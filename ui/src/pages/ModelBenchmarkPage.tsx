import React, { useState, useEffect, useCallback } from 'react';
import { ModelBenchmark, ModelBenchmarksResponse, RequestLogEntry, RequestLogsResponse, Account } from '../types';
import { useToast } from '../context/ToastContext';
import { useModal } from '../context/ModalContext';
import {
  BarChart3,
  Flame,
  Zap,
  Clock,
  Database,
  RefreshCw,
  Trash2,
  Search,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
  TrendingUp,
  Cpu,
  Layers,
  Sparkles,
  ArrowUpRight,
} from 'lucide-react';

interface ModelBenchmarkPageProps {
  activeAccount: Account | null;
  lastLedgerUpdate?: number;
  isWsConnected?: boolean;
}

export const ModelBenchmarkPage: React.FC<ModelBenchmarkPageProps> = ({
  activeAccount,
  lastLedgerUpdate,
  isWsConnected = false,
}) => {
  const { showToast } = useToast();
  const { openModal, closeModal } = useModal();

  const [benchmarkData, setBenchmarkData] = useState<ModelBenchmarksResponse | null>(null);
  const [logsData, setLogsData] = useState<RequestLogsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('all');
  const [page, setPage] = useState<number>(0);
  const pageSize = 25;

  const fetchBenchmarks = useCallback(async () => {
    try {
      const res = await fetch('/api/analytics/models');
      if (res.ok) {
        const data: ModelBenchmarksResponse = await res.json();
        setBenchmarkData(data);
      }
    } catch (err) {
      console.error('Failed to fetch model benchmarks:', err);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      let url = `/api/analytics/requests?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedModel !== 'all') {
        url += `&model=${encodeURIComponent(selectedModel)}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data: RequestLogsResponse = await res.json();
        setLogsData(data);
      }
    } catch (err) {
      console.error('Failed to fetch request logs:', err);
    }
  }, [page, pageSize, selectedModel]);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([fetchBenchmarks(), fetchLogs()]);
    setIsRefreshing(false);
  }, [fetchBenchmarks, fetchLogs]);

  // Initial load
  useEffect(() => {
    setIsLoading(true);
    Promise.all([fetchBenchmarks(), fetchLogs()]).finally(() => {
      setIsLoading(false);
    });
  }, [fetchBenchmarks, fetchLogs]);

  // Real-time sync on WebSocket event push
  useEffect(() => {
    if (!lastLedgerUpdate) return;
    fetchBenchmarks();
    if (page === 0 && !searchQuery) {
      fetchLogs();
    }
  }, [lastLedgerUpdate, fetchBenchmarks, fetchLogs, page, searchQuery]);

  // Fallback heartbeat polling every 3 seconds to guarantee 100% sync
  useEffect(() => {
    const timer = setInterval(() => {
      fetchBenchmarks();
      if (page === 0 && !searchQuery) {
        fetchLogs();
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [fetchBenchmarks, fetchLogs, page, searchQuery]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(text);
      setTimeout(() => setCopiedId(null), 2000);
      showToast('Copied to clipboard', 'info');
    });
  };

  const handleClearLogs = () => {
    openModal({
      title: 'Clear Request Hit Ledger',
      description: 'Are you sure you want to delete all historical request logs from the database? This action cannot be undone.',
      confirmText: 'Clear All Logs',
      confirmVariant: 'danger',
      onConfirm: async () => {
        try {
          const res = await fetch('/api/analytics/requests', { method: 'DELETE' });
          if (res.ok) {
            showToast('All request hits successfully cleared from database', 'success');
            await refreshAll();
          } else {
            showToast('Failed to clear request logs', 'error');
          }
        } catch (e) {
          showToast('Failed to clear request logs', 'error');
        }
      },
    });
  };

  const models = benchmarkData?.models || [];
  const topSpender = models.length > 0 ? models[0] : null;

  // Heaviest quota consumer by quota impact score
  const heaviestQuotaModel = models.length > 0
    ? [...models].sort((a, b) => b.quota_impact_score - a.quota_impact_score)[0]
    : null;

  // Fastest model by avg latency
  const fastestModel = models.length > 0
    ? [...models].filter(m => m.avg_latency_ms > 0).sort((a, b) => a.avg_latency_ms - b.avg_latency_ms)[0]
    : null;

  const filteredLogs = (logsData?.logs || []).filter(log => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      log.model.toLowerCase().includes(q) ||
      log.request_id.toLowerCase().includes(q) ||
      log.account_email.toLowerCase().includes(q)
    );
  });

  const totalPages = Math.ceil((logsData?.total || 0) / pageSize);

  const getQuotaImpactBadge = (score: number) => {
    if (score >= 60) {
      return <span className="badge badge-rose">Severe ({score})</span>;
    } else if (score >= 30) {
      return <span className="badge badge-amber">Heavy ({score})</span>;
    } else if (score >= 10) {
      return <span className="badge badge-blue">Moderate ({score})</span>;
    }
    return <span className="badge badge-emerald">Light ({score})</span>;
  };

  const getLatencyBadge = (ms: number) => {
    if (ms <= 1500) {
      return <span style={{ color: '#10b981', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{ms.toFixed(0)} ms</span>;
    } else if (ms <= 4000) {
      return <span style={{ color: '#f59e0b', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{ms.toFixed(0)} ms</span>;
    }
    return <span style={{ color: '#f43f5e', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{ms.toFixed(0)} ms</span>;
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
              }}
            >
              <BarChart3 size={20} />
            </div>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
                Model Benchmarks & Request Hit Ledger
              </h1>
              <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 2 }}>
                Persistent request tracking, latency benchmarks, token volume, and quota consumption analytics.
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              borderRadius: 20,
              background: isWsConnected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
              border: `1px solid ${isWsConnected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            }}
            title={isWsConnected ? 'Connected to live WebSocket stream' : 'Syncing via periodic background polling'}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: isWsConnected ? '#10b981' : '#f59e0b',
                boxShadow: isWsConnected ? '0 0 8px #10b981' : 'none',
              }}
            />
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: isWsConnected ? '#10b981' : '#f59e0b',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              {isWsConnected ? 'LIVE REALTIME' : 'POLLING SYNC'}
            </span>
          </div>

          <button
            onClick={refreshAll}
            disabled={isRefreshing}
            className="btn btn-secondary btn-sm"
          >
            <RefreshCw size={14} style={{ animation: isRefreshing ? 'spin 1s linear infinite' : 'none' }} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
          <button
            onClick={handleClearLogs}
            className="btn btn-secondary btn-sm"
            style={{ color: '#f43f5e', borderColor: 'rgba(244, 63, 94, 0.3)' }}
          >
            <Trash2 size={14} />
            <span>Clear Ledger</span>
          </button>
        </div>
      </div>

      {/* 4 Summary Analytics KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16,
        }}
      >
        {/* Card 1: Top Token Spender */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Top Token Spender</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
              }}
            >
              <TrendingUp size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {topSpender ? topSpender.model : 'No hits yet'}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                {topSpender ? topSpender.total_tokens.toLocaleString() : '0'}
              </span>
              <span style={{ fontSize: 12, color: '#78716c' }}>
                tokens ({topSpender ? `${topSpender.token_share_pct}%` : '0%'})
              </span>
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            Consumed highest total volume
          </div>
        </div>

        {/* Card 2: Heaviest Quota Consumer */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Heaviest Quota Consumer</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(244, 63, 94, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f43f5e',
              }}
            >
              <Flame size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {heaviestQuotaModel ? heaviestQuotaModel.model : 'No hits yet'}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: '#f43f5e', fontFamily: 'var(--font-mono)' }}>
                {heaviestQuotaModel ? heaviestQuotaModel.quota_impact_score : '0.0'}
              </span>
              <span style={{ fontSize: 12, color: '#78716c' }}>Quota Impact Score</span>
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            Weight factor: Claude (3x), GPT (2x), Gemini (1x)
          </div>
        </div>

        {/* Card 3: Fastest Model */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Lowest Latency Model</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10b981',
              }}
            >
              <Zap size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {fastestModel ? fastestModel.model : 'N/A'}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                {fastestModel ? `${fastestModel.avg_latency_ms.toFixed(0)} ms` : '0 ms'}
              </span>
              <span style={{ fontSize: 12, color: '#78716c' }}>
                {fastestModel && fastestModel.tokens_per_second > 0 ? `(~${fastestModel.tokens_per_second} tok/s)` : ''}
              </span>
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            Fastest response generation
          </div>
        </div>

        {/* Card 4: Total Logged Hits */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Total Ledger Hits</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(59, 130, 246, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#3b82f6',
              }}
            >
              <Database size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', fontFamily: 'var(--font-mono)' }}>
                {(logsData?.total || 0).toLocaleString()}
              </span>
              <span style={{ fontSize: 13, color: '#78716c' }}>hits recorded</span>
            </div>
            <div style={{ fontSize: 12, color: '#78716c', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
              Total Volume: {(benchmarkData?.total_tokens || 0).toLocaleString()} tokens
              {(benchmarkData?.total_tokens_saved || 0) > 0 && (
                <span style={{ color: '#10b981', marginLeft: 8, fontWeight: 600 }}>
                  ⚡ Saved: {(benchmarkData?.total_tokens_saved || 0).toLocaleString()} tok
                </span>
              )}
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            {(benchmarkData?.total_cache_hits || 0) > 0
              ? `${(benchmarkData?.total_cache_hits || 0)} cache hits automatically accumulated`
              : 'SQLite WAL ledger with CRC32 integrity'}
          </div>
        </div>
      </div>

      {/* Model Benchmark & Quota Impact Comparison Table */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#ffffff' }}>
              Model Consumption & Performance Rankings
            </h2>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
              Aggregated statistics per model across all API requests. Sorted by total token consumption.
            </p>
          </div>
          <span className="badge badge-amber">{models.length} Models Tracked</span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#a8a29e', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '12px 14px' }}>Model</th>
                <th style={{ padding: '12px 14px' }}>Requests</th>
                <th style={{ padding: '12px 14px' }}>Prompt Tokens</th>
                <th style={{ padding: '12px 14px' }}>Completion</th>
                <th style={{ padding: '12px 14px' }}>Reasoning (Think)</th>
                <th style={{ padding: '12px 14px' }}>Total Tokens & Share</th>
                <th style={{ padding: '12px 14px' }}>Avg Latency</th>
                <th style={{ padding: '12px 14px' }}>Quota Impact</th>
              </tr>
            </thead>
            <tbody>
              {models.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '36px 0', color: '#78716c' }}>
                    No request hits logged yet. Execute chat completion requests to generate benchmarks.
                  </td>
                </tr>
              ) : (
                models.map((m, idx) => {
                  const sharePct = m.token_share_pct;
                  const barColor = sharePct > 50 ? '#f59e0b' : sharePct > 20 ? '#3b82f6' : '#10b981';

                  return (
                    <tr
                      key={m.model}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <td style={{ padding: '14px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontWeight: 600, color: '#fafaf9', fontFamily: 'var(--font-mono)' }}>
                            {m.model}
                          </span>
                          {idx === 0 && <span className="badge badge-amber" style={{ fontSize: 10 }}>#1 Spender</span>}
                        </div>
                        <div style={{ fontSize: 11, color: '#78716c', marginTop: 2 }}>
                          Last seen: {m.last_seen_formatted}
                        </div>
                      </td>

                      <td style={{ padding: '14px 14px', fontFamily: 'var(--font-mono)', color: '#d6d3d1' }}>
                        {m.requests_count.toLocaleString()}
                      </td>

                      <td style={{ padding: '14px 14px', fontFamily: 'var(--font-mono)', color: '#a8a29e' }}>
                        {m.prompt_tokens.toLocaleString()}
                      </td>

                      <td style={{ padding: '14px 14px', fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
                        {m.completion_tokens.toLocaleString()}
                      </td>

                      <td style={{ padding: '14px 14px', fontFamily: 'var(--font-mono)', color: '#a78bfa' }}>
                        {m.reasoning_tokens.toLocaleString()}
                      </td>

                      <td style={{ padding: '14px 14px', minWidth: 160 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontWeight: 700, color: '#ffffff', fontFamily: 'var(--font-mono)' }}>
                            {m.total_tokens.toLocaleString()}
                          </span>
                          <span style={{ fontSize: 11, color: barColor, fontWeight: 600 }}>
                            {sharePct}%
                          </span>
                        </div>
                        <div style={{ height: 5, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 4, overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${Math.min(100, Math.max(2, sharePct))}%`,
                              height: '100%',
                              background: barColor,
                              borderRadius: 4,
                            }}
                          />
                        </div>
                        {(m.tokens_saved || 0) > 0 && (
                          <div style={{ fontSize: 10, color: '#10b981', marginTop: 4, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Zap size={10} /> {(m.tokens_saved || 0).toLocaleString()} saved ({m.cache_hits || 0} hits)
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 14px' }}>
                        {getLatencyBadge(m.avg_latency_ms)}
                        {m.tokens_per_second > 0 && (
                          <div style={{ fontSize: 10, color: '#78716c', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                            {m.tokens_per_second} tok/s
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 14px' }}>
                        {getQuotaImpactBadge(m.quota_impact_score)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Granular Request Hit Ledger */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14, marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#ffffff' }}>
              Granular Request Hit Ledger
            </h2>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
              Every inbound API request recorded with exact timestamp, token splits, latency, and quota snapshots.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {/* Search Input */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: 'rgba(0, 0, 0, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 8,
                padding: '6px 12px',
              }}
            >
              <Search size={14} color="#78716c" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search model, ID, account..."
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#fafaf9',
                  fontSize: 13,
                  outline: 'none',
                  width: 180,
                }}
              />
            </div>

            {/* Model Filter Dropdown */}
            <select
              value={selectedModel}
              onChange={e => {
                setSelectedModel(e.target.value);
                setPage(0);
              }}
              className="btn btn-secondary btn-sm"
              style={{
                background: 'rgba(0, 0, 0, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#fafaf9',
                cursor: 'pointer',
              }}
            >
              <option value="all">All Models</option>
              {models.map(m => (
                <option key={m.model} value={m.model}>
                  {m.model}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Ledger Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#a8a29e', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '12px 12px' }}>Timestamp</th>
                <th style={{ padding: '12px 12px' }}>Request ID</th>
                <th style={{ padding: '12px 12px' }}>Model</th>
                <th style={{ padding: '12px 12px' }}>Account</th>
                <th style={{ padding: '12px 12px' }}>Token Breakdown</th>
                <th style={{ padding: '12px 12px' }}>Total</th>
                <th style={{ padding: '12px 12px' }}>Latency</th>
                <th style={{ padding: '12px 12px' }}>Mode</th>
                <th style={{ padding: '12px 12px' }}>Quota Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '36px 0', color: '#78716c' }}>
                    No matching request hits found in database.
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => {
                  const isCopied = copiedId === log.request_id;
                  return (
                    <tr
                      key={log.id}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      {/* Timestamp */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', color: '#a8a29e', fontFamily: 'var(--font-mono)' }}>
                        {log.time_formatted}
                      </td>

                      {/* Request ID */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontFamily: 'var(--font-mono)', color: '#78716c', fontSize: 11 }}>
                            {log.request_id.length > 18 ? `${log.request_id.slice(0, 16)}...` : log.request_id}
                          </span>
                          <button
                            onClick={() => handleCopy(log.request_id)}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              padding: 2,
                              color: isCopied ? '#10b981' : '#78716c',
                            }}
                            title="Copy Request ID"
                          >
                            {isCopied ? <Check size={12} /> : <Copy size={12} />}
                          </button>
                        </div>
                      </td>

                      {/* Model */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        <span className="badge badge-amber" style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                          {log.model}
                        </span>
                      </td>

                      {/* Account */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', color: '#d6d3d1' }}>
                        {log.account_email}
                      </td>

                      {/* Token Breakdown */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                        {log.cache_hit ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                            {log.cache_hit_type === 2 ? (
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 3,
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  background: 'rgba(167, 139, 250, 0.15)',
                                  border: '1px solid rgba(167, 139, 250, 0.3)',
                                  color: '#c4b5fd',
                                }}
                              >
                                <Zap size={10} /> SEMANTIC HIT {log.similarity_score ? `(${(log.similarity_score * 100).toFixed(1)}%)` : ''}
                              </span>
                            ) : log.cache_hit_type === 3 ? (
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 3,
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  background: 'rgba(56, 189, 248, 0.15)',
                                  border: '1px solid rgba(56, 189, 248, 0.3)',
                                  color: '#38bdf8',
                                }}
                              >
                                <Zap size={10} /> UPSTREAM PREFIX
                              </span>
                            ) : (
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 3,
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  background: 'rgba(16, 185, 129, 0.15)',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                  color: '#34d399',
                                }}
                              >
                                <Zap size={10} /> EXACT HIT
                              </span>
                            )}
                            <span style={{ color: '#10b981', fontWeight: 600 }}>
                              +{(log.tokens_saved || log.total_tokens).toLocaleString()} saved
                            </span>
                            <span style={{ color: '#78716c', fontSize: 10 }}>
                              (P:{log.prompt_tokens} &bull; C:{log.completion_tokens})
                            </span>
                          </div>
                        ) : (
                          <div>
                            <span style={{ color: '#a8a29e' }} title="Prompt Tokens">P: {log.prompt_tokens}</span>
                            {' '}&bull;{' '}
                            <span style={{ color: '#38bdf8' }} title="Completion Tokens">C: {log.completion_tokens}</span>
                            {log.reasoning_tokens > 0 && (
                              <>
                                {' '}&bull;{' '}
                                <span style={{ color: '#a78bfa' }} title="Reasoning Tokens">T: {log.reasoning_tokens}</span>
                              </>
                            )}
                          </div>
                        )}
                      </td>

                      {/* Total Tokens */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                        <div style={{ fontWeight: 700, color: log.cache_hit ? '#34d399' : '#ffffff' }}>
                          {log.total_tokens.toLocaleString()}
                        </div>
                        {log.cache_hit && (
                          <div style={{ fontSize: 10, color: '#10b981', fontWeight: 600 }}>
                            ⚡ 0 upstream
                          </div>
                        )}
                      </td>

                      {/* Latency */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        {getLatencyBadge(log.latency_ms)}
                      </td>

                      {/* Mode (Stream / Rest) */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        <span className={log.stream ? 'badge badge-emerald' : 'badge badge-neutral'} style={{ fontSize: 10 }}>
                          {log.stream ? 'SSE Stream' : 'REST'}
                        </span>
                      </td>

                      {/* Quota Snapshot */}
                      <td style={{ padding: '12px 12px' }}>
                        {log.quota_snapshot && Array.isArray(log.quota_snapshot) && log.quota_snapshot.length > 0 ? (
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {log.quota_snapshot.slice(0, 2).map((qb, qidx) => (
                              <span
                                key={qidx}
                                style={{
                                  fontSize: 10,
                                  fontFamily: 'var(--font-mono)',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  background: 'rgba(255, 255, 255, 0.05)',
                                  color: qb.percentage < 20 ? '#f43f5e' : '#10b981',
                                }}
                              >
                                {qb.family}: {qb.percentage.toFixed(0)}%
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: '#57534e', fontSize: 11 }}>Active</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 18, paddingTop: 14, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <div style={{ fontSize: 12, color: '#78716c' }}>
            Showing {filteredLogs.length} of {(logsData?.total || 0).toLocaleString()} hits &bull; Page {page + 1} of {Math.max(1, totalPages)}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="btn btn-secondary btn-sm"
              style={{ opacity: page === 0 ? 0.4 : 1 }}
            >
              <ChevronLeft size={14} />
              <span>Previous</span>
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page + 1 >= totalPages}
              className="btn btn-secondary btn-sm"
              style={{ opacity: page + 1 >= totalPages ? 0.4 : 1 }}
            >
              <span>Next</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
