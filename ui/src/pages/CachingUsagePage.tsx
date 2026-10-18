import React, { useState, useEffect, useCallback } from 'react';
import { CacheStats, CacheEntry, CacheEntriesResponse, CacheConfig } from '../types';
import { useToast } from '../context/ToastContext';
import { useModal } from '../context/ModalContext';
import {
  Zap,
  RefreshCw,
  Trash2,
  Search,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
  TrendingUp,
  Clock,
  Shield,
  Layers,
  Settings,
  Flame,
  CheckCircle2,
  XCircle,
  Eye,
} from 'lucide-react';

interface CachingUsagePageProps {
  lastLedgerUpdate?: number;
  isWsConnected?: boolean;
}

export const CachingUsagePage: React.FC<CachingUsagePageProps> = ({
  lastLedgerUpdate,
  isWsConnected = false,
}) => {
  const { showToast } = useToast();
  const { openModal, closeModal } = useModal();

  const [stats, setStats] = useState<CacheStats | null>(null);
  const [entriesData, setEntriesData] = useState<CacheEntriesResponse | null>(null);
  const [config, setConfig] = useState<CacheConfig>({
    enabled: true,
    bypass_tools: true,
    min_prompt_length: 5,
    ttl_seconds: 604800,
  });

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isSavingConfig, setIsSavingConfig] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [page, setPage] = useState<number>(0);
  const pageSize = 20;

  // Fetch cache stats & config
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/cache/stats');
      if (res.ok) {
        const data: CacheStats = await res.json();
        setStats(data);
        if (data.config) {
          setConfig(data.config);
        }
      }
    } catch (err) {
      console.error('Failed to fetch cache stats:', err);
    }
  }, []);

  // Fetch cached prompt entries
  const fetchEntries = useCallback(async () => {
    try {
      let url = `/api/cache/entries?limit=${pageSize}&offset=${page * pageSize}`;
      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data: CacheEntriesResponse = await res.json();
        setEntriesData(data);
      }
    } catch (err) {
      console.error('Failed to fetch cache entries:', err);
    }
  }, [page, pageSize, searchQuery]);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([fetchStats(), fetchEntries()]);
    setIsRefreshing(false);
  }, [fetchStats, fetchEntries]);

  // Initial load
  useEffect(() => {
    setIsLoading(true);
    Promise.all([fetchStats(), fetchEntries()]).finally(() => {
      setIsLoading(false);
    });
  }, [fetchStats, fetchEntries]);

  // Auto-refresh when WebSocket broadcasts updates
  useEffect(() => {
    if (!lastLedgerUpdate) return;
    fetchStats();
    if (page === 0) {
      fetchEntries();
    }
  }, [lastLedgerUpdate, fetchStats, fetchEntries, page]);

  // Copy helper
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    showToast('Copied to clipboard', 'info');
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  // Save cache configuration
  const handleSaveConfig = async (newCfg: Partial<CacheConfig>) => {
    try {
      setIsSavingConfig(true);
      const updated = { ...config, ...newCfg };
      const res = await fetch('/api/cache/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
      if (!res.ok) throw new Error('Failed to update cache settings');
      const data = await res.json();
      if (data.config) {
        setConfig(data.config);
      }
      showToast('Cache configuration updated successfully', 'success');
      fetchStats();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to update config', 'error');
    } finally {
      setIsSavingConfig(false);
    }
  };

  // Clear entire cache confirmation modal
  const handleClearCacheModal = () => {
    openModal({
      title: 'Purge Smart Semantic Cache',
      description: 'Are you sure you want to delete all cached prompt/response entries? Subsequent requests will execute full upstream Antigravity inference.',
      confirmText: 'Purge Entire Cache',
      cancelText: 'Cancel',
      confirmVariant: 'danger',
      onConfirm: async () => {
        try {
          const res = await fetch('/api/cache/clear', { method: 'POST' });
          if (res.ok) {
            showToast('Smart Cache purged successfully', 'success');
            refreshAll();
          } else {
            throw new Error('Failed to clear cache');
          }
        } catch (err: unknown) {
          showToast((err as Error).message || 'Failed to clear cache', 'error');
        }
      },
    });
  };

  // Delete single cache entry
  const handleDeleteEntry = async (entryId: number) => {
    try {
      const res = await fetch(`/api/cache/entries/${entryId}`, { method: 'DELETE' });
      if (res.ok) {
        showToast('Cache entry deleted', 'success');
        refreshAll();
      } else {
        throw new Error('Failed to delete cache entry');
      }
    } catch (err: unknown) {
      showToast((err as Error).message || 'Delete failed', 'error');
    }
  };

  // View full response modal
  const handleViewDetails = (entry: CacheEntry) => {
    openModal({
      title: `Cached Prompt & Response Details`,
      description: `Model: ${entry.model} | Cache Key: ${entry.cache_key}`,
      cancelText: 'Close',
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6 }}>
              Prompt Preview:
            </div>
            <pre
              style={{
                background: 'rgba(0, 0, 0, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                padding: '12px 14px',
                borderRadius: 8,
                fontSize: 12,
                color: '#fafaf9',
                maxHeight: 140,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {entry.prompt_preview || '(No preview)'}
            </pre>
          </div>

          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6 }}>
              Cached Assistant Response:
            </div>
            <pre
              style={{
                background: 'rgba(0, 0, 0, 0.5)',
                border: '1px solid rgba(16, 185, 129, 0.2)',
                padding: '12px 14px',
                borderRadius: 8,
                fontSize: 12,
                color: '#34d399',
                maxHeight: 220,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {entry.response_text}
            </pre>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 8,
              background: 'rgba(255, 255, 255, 0.03)',
              padding: 12,
              borderRadius: 8,
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <div>
              <span style={{ color: '#78716c' }}>Hits: </span>
              <span style={{ color: '#ffffff', fontWeight: 700 }}>{entry.hit_count}x</span>
            </div>
            <div>
              <span style={{ color: '#78716c' }}>Tokens: </span>
              <span style={{ color: '#38bdf8', fontWeight: 700 }}>{entry.total_tokens}</span>
            </div>
            <div>
              <span style={{ color: '#78716c' }}>Total Saved: </span>
              <span style={{ color: '#10b981', fontWeight: 700 }}>{entry.tokens_saved_total.toLocaleString()}</span>
            </div>
            <div>
              <span style={{ color: '#78716c' }}>Split: </span>
              <span style={{ color: '#a8a29e' }}>P:{entry.prompt_tokens} C:{entry.completion_tokens}</span>
            </div>
          </div>
        </div>
      ),
    });
  };

  const entries = entriesData?.entries || [];
  const totalEntriesCount = entriesData?.total || 0;
  const totalPages = Math.ceil(totalEntriesCount / pageSize);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Header & Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10b981',
              }}
            >
              <Zap size={20} />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
              Smart Semantic Caching Usage
            </h1>
          </div>
          <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4 }}>
            Zero-quota prompt caching layer. Intercepts identical requests, delivers ~5ms response times, and preserves upstream quota.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {/* WebSocket Status Indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              padding: '6px 12px',
              borderRadius: 8,
            }}
          >
            <div
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
            onClick={handleClearCacheModal}
            className="btn btn-secondary btn-sm"
            style={{ color: '#f43f5e', borderColor: 'rgba(244, 63, 94, 0.3)' }}
          >
            <Trash2 size={14} />
            <span>Purge Cache</span>
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
        {/* Card 1: Total Tokens Saved */}
        <div className="glass-card" style={{ padding: '20px 24px', borderLeft: '4px solid #10b981' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Total Tokens Saved</span>
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
            <div style={{ fontSize: 26, fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
              {(stats?.total_tokens_saved || 0).toLocaleString()}
            </div>
            <div style={{ fontSize: 12, color: '#78716c', marginTop: 4 }}>
              Zero upstream tokens consumed
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#10b981', marginTop: 8, fontWeight: 600 }}>
            ⚡ 100% Free quota execution
          </div>
        </div>

        {/* Card 2: Cache Hit Ratio */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Cache Hit Ratio</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(56, 189, 248, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
              }}
            >
              <TrendingUp size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', fontFamily: 'var(--font-mono)' }}>
              {(stats?.hit_ratio_pct || 0).toFixed(1)}%
            </div>
            <div style={{ fontSize: 12, color: '#78716c', marginTop: 4 }}>
              {(stats?.total_hits || 0).toLocaleString()} total cache hits
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            Intercepted before reaching Google Antigravity
          </div>
        </div>

        {/* Card 3: Active Cache Entries */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Active Cache Entries</span>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(167, 139, 250, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#a78bfa',
              }}
            >
              <Layers size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', fontFamily: 'var(--font-mono)' }}>
              {(stats?.total_entries || 0).toLocaleString()}
            </div>
            <div style={{ fontSize: 12, color: '#78716c', marginTop: 4 }}>
              Unique prompt patterns stored
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            SQLite WAL database with CRC32 integrity
          </div>
        </div>

        {/* Card 4: Estimated Latency Saved */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Estimated Latency Saved</span>
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
              <Clock size={16} />
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
              {(stats?.estimated_seconds_saved || 0).toFixed(1)}s
            </div>
            <div style={{ fontSize: 12, color: '#78716c', marginTop: 4 }}>
              Saved waiting time across hits
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 8 }}>
            Average ~5ms TTFT response delivery
          </div>
        </div>
      </div>

      {/* Smart Cache Configuration & Controls */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Settings size={18} color="#38bdf8" />
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
            Smart Cache Engine Settings & Safety Boundaries
          </h2>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 20,
          }}
        >
          {/* Toggle 1: Smart Cache Enabled */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              padding: '16px 18px',
              borderRadius: 10,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                Enable Smart Semantic Cache
              </div>
              <div style={{ fontSize: 12, color: '#a8a29e', marginTop: 4, lineHeight: 1.4 }}>
                When enabled, requests with identical model and messages receive instantaneous cached responses.
              </div>
            </div>
            <button
              onClick={() => handleSaveConfig({ enabled: !config.enabled })}
              disabled={isSavingConfig}
              className={`btn btn-sm ${config.enabled ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                marginLeft: 16,
                padding: '6px 14px',
                minWidth: 80,
                background: config.enabled ? '#10b981' : undefined,
                borderColor: config.enabled ? '#10b981' : undefined,
                color: '#ffffff',
              }}
            >
              {config.enabled ? 'Enabled' : 'Disabled'}
            </button>
          </div>

          {/* Toggle 2: Agent Safety Boundary (Bypass on Tools) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              padding: '16px 18px',
              borderRadius: 10,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                  Bypass on Dynamic Tools (Agent Safe)
                </span>
                <span className="badge badge-amber" style={{ fontSize: 10 }}>Recommended</span>
              </div>
              <div style={{ fontSize: 12, color: '#a8a29e', marginTop: 4, lineHeight: 1.4 }}>
                Prevents stale state when AI coding agents execute file operations, terminal commands, or live tools.
              </div>
            </div>
            <button
              onClick={() => handleSaveConfig({ bypass_tools: !config.bypass_tools })}
              disabled={isSavingConfig}
              className={`btn btn-sm ${config.bypass_tools ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                marginLeft: 16,
                padding: '6px 14px',
                minWidth: 80,
                background: config.bypass_tools ? '#38bdf8' : undefined,
                borderColor: config.bypass_tools ? '#38bdf8' : undefined,
                color: '#ffffff',
              }}
            >
              {config.bypass_tools ? 'Active' : 'Off'}
            </button>
          </div>
        </div>
      </div>

      {/* Cached Entries Table */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14, marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#ffffff' }}>
              Persistent Cache Ledger ({totalEntriesCount})
            </h2>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
              Inspect all stored prompt patterns, cached responses, hit counters, and accumulated token savings.
            </p>
          </div>

          {/* Search Box */}
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
              onChange={e => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
              placeholder="Search prompt, model..."
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fafaf9',
                fontSize: 13,
                outline: 'none',
                width: 220,
              }}
            />
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#a8a29e', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '12px 12px' }}>Model</th>
                <th style={{ padding: '12px 12px' }}>Prompt Preview</th>
                <th style={{ padding: '12px 12px' }}>Response Preview</th>
                <th style={{ padding: '12px 12px' }}>Tokens</th>
                <th style={{ padding: '12px 12px' }}>Hit Count</th>
                <th style={{ padding: '12px 12px' }}>Tokens Saved</th>
                <th style={{ padding: '12px 12px' }}>Last Hit</th>
                <th style={{ padding: '12px 12px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '36px 0', color: '#78716c' }}>
                    {searchQuery ? 'No matching cache entries found.' : 'No responses cached yet. Run prompts to populate the cache!'}
                  </td>
                </tr>
              ) : (
                entries.map(entry => {
                  const isCopied = copiedKey === entry.cache_key;
                  return (
                    <tr
                      key={entry.id}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      {/* Model */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        <span className="badge badge-amber" style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                          {entry.model}
                        </span>
                      </td>

                      {/* Prompt Preview */}
                      <td style={{ padding: '12px 12px', maxWidth: 220 }}>
                        <div
                          style={{
                            color: '#e7e5e4',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={entry.prompt_preview}
                        >
                          {entry.prompt_preview || '(No preview)'}
                        </div>
                      </td>

                      {/* Response Preview */}
                      <td style={{ padding: '12px 12px', maxWidth: 240 }}>
                        <div
                          style={{
                            color: '#a8a29e',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 11,
                          }}
                          title={entry.response_text}
                        >
                          {entry.response_text}
                        </div>
                      </td>

                      {/* Tokens */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                        <span style={{ color: '#ffffff', fontWeight: 600 }}>{entry.total_tokens}</span>
                        <div style={{ color: '#78716c', fontSize: 10 }}>
                          P:{entry.prompt_tokens} &bull; C:{entry.completion_tokens}
                        </div>
                      </td>

                      {/* Hit Count */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap' }}>
                        <span
                          className={entry.hit_count > 0 ? 'badge badge-emerald' : 'badge badge-neutral'}
                          style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)' }}
                        >
                          {entry.hit_count}x
                        </span>
                      </td>

                      {/* Tokens Saved */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                        <span style={{ color: entry.tokens_saved_total > 0 ? '#10b981' : '#78716c', fontWeight: 700 }}>
                          {entry.tokens_saved_total.toLocaleString()}
                        </span>
                      </td>

                      {/* Last Hit */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', color: '#a8a29e', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                        {entry.last_hit_formatted || 'Never'}
                      </td>

                      {/* Actions */}
                      <td style={{ padding: '12px 12px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                          <button
                            onClick={() => handleViewDetails(entry)}
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '4px 8px' }}
                            title="View Full Content"
                          >
                            <Eye size={12} />
                          </button>
                          <button
                            onClick={() => handleCopy(entry.cache_key, entry.cache_key)}
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '4px 8px', color: isCopied ? '#10b981' : undefined }}
                            title="Copy Cache Key"
                          >
                            {isCopied ? <Check size={12} /> : <Copy size={12} />}
                          </button>
                          <button
                            onClick={() => handleDeleteEntry(entry.id)}
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '4px 8px', color: '#f43f5e', borderColor: 'rgba(244, 63, 94, 0.3)' }}
                            title="Delete Cache Entry"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 18, paddingTop: 14, borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <span style={{ fontSize: 12, color: '#78716c' }}>
              Showing {page * pageSize + 1} - {Math.min((page + 1) * pageSize, totalEntriesCount)} of {totalEntriesCount}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="btn btn-secondary btn-sm"
              >
                <ChevronLeft size={14} />
                <span>Prev</span>
              </button>
              <span style={{ fontSize: 12, color: '#a8a29e', fontFamily: 'var(--font-mono)', padding: '0 4px' }}>
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="btn btn-secondary btn-sm"
              >
                <span>Next</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
