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
  CheckCircle2,
  XCircle,
  Eye,
  Sliders,
  Database,
  Cpu,
  Minimize2,
  ShieldAlert,
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
  const { openModal } = useModal();

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
    const responseContent = entry.response_text || entry.response_preview || '(No response text captured)';
    openModal({
      title: `Cached Prompt & Response Details`,
      description: `Model: ${entry.model} | Cache Key: ${entry.cache_key}`,
      cancelText: 'Close',
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6 }}>
              Prompt Content:
            </div>
            <pre
              style={{
                background: 'rgba(0, 0, 0, 0.45)',
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
                background: 'rgba(0, 0, 0, 0.55)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                padding: '12px 14px',
                borderRadius: 8,
                fontSize: 12,
                color: '#34d399',
                maxHeight: 240,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {responseContent}
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
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Action Triggers */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
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

      {/* 4 Summary Analytics KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16,
        }}
      >
        {/* Card 1: Total Tokens Saved */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
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
          <div style={{ fontSize: 11, color: '#10b981', marginTop: 8, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>⚡ 100% Free quota execution</span>
            <span style={{ color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>
              {stats?.idr_value_saved ? `Rp ${stats.idr_value_saved.toLocaleString('id-ID')}` : '$0.00'}
            </span>
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
            Average ~3ms TTFT response delivery
          </div>
        </div>
      </div>

      {/* Smart Cache Configuration & Controls */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Settings size={18} color="#38bdf8" />
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
              Smart Cache Engine Settings & Safety Boundaries
            </h2>
          </div>
          <span style={{ fontSize: 12, color: '#78716c' }}>
            Instant dynamic persistence in SQLite WAL
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 16,
          }}
        >
          {/* Card 1: Smart Cache Enabled */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Zap size={16} color={config.enabled ? '#34d399' : '#78716c'} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Smart Semantic Cache
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 12,
                    background: config.enabled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                    color: config.enabled ? '#34d399' : '#78716c',
                    border: `1px solid ${config.enabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
                  }}
                >
                  {config.enabled ? 'ACTIVE' : 'OFF'}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                When enabled, requests with identical model and messages receive instantaneous cached responses without consuming quota.
              </p>
            </div>

            <div style={{ marginTop: 18 }}>
              <button
                onClick={() => handleSaveConfig({ enabled: !config.enabled })}
                disabled={isSavingConfig}
                className={`btn btn-sm ${config.enabled ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '7px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  background: config.enabled ? '#10b981' : undefined,
                  borderColor: config.enabled ? '#10b981' : undefined,
                  color: '#ffffff',
                }}
              >
                {config.enabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          </div>

          {/* Card 2: Agent Safety Boundary (Bypass on Tools) */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Shield size={16} color={config.bypass_tools ? '#38bdf8' : '#78716c'} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Bypass Dynamic Tools
                  </span>
                </div>
                <span className="badge badge-amber" style={{ fontSize: 10, padding: '2px 6px' }}>Recommended</span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                Prevents stale state when AI coding agents execute file operations, terminal commands, or live dynamic tools.
              </p>
            </div>

            <div style={{ marginTop: 18 }}>
              <button
                onClick={() => handleSaveConfig({ bypass_tools: !config.bypass_tools })}
                disabled={isSavingConfig}
                className={`btn btn-sm ${config.bypass_tools ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '7px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  background: config.bypass_tools ? '#38bdf8' : undefined,
                  borderColor: config.bypass_tools ? '#38bdf8' : undefined,
                  color: '#ffffff',
                }}
              >
                {config.bypass_tools ? 'Active (Safe)' : 'Off'}
              </button>
            </div>
          </div>

          {/* Card 3: Min Prompt Length */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Cpu size={16} color="#a78bfa" />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Minimum Prompt Length
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    color: '#c4b5fd',
                  }}
                >
                  {config.min_prompt_length} chars
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                Short greetings or single-word inputs under this character count will skip cache storage.
              </p>
            </div>

            <div style={{ marginTop: 18 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 6,
                  background: 'rgba(255, 255, 255, 0.04)',
                  padding: 3,
                  borderRadius: 8,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                {[
                  { len: 5, label: '5 chars' },
                  { len: 10, label: '10 chars' },
                  { len: 25, label: '25 chars' },
                ].map(item => {
                  const isActive = config.min_prompt_length === item.len;
                  return (
                    <button
                      key={item.len}
                      onClick={() => handleSaveConfig({ min_prompt_length: item.len })}
                      disabled={isSavingConfig}
                      style={{
                        padding: '6px 0',
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        fontFamily: 'var(--font-mono)',
                        textAlign: 'center',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? '#a78bfa' : 'transparent',
                        color: isActive ? '#ffffff' : '#a8a29e',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Card 4: Cache Retention TTL */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Clock size={16} color="#f59e0b" />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Cache Retention (TTL)
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    color: '#fbbf24',
                  }}
                >
                  {config.ttl_seconds === 604800 ? '7 Days' : config.ttl_seconds === 1209600 ? '14 Days' : '30 Days'}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                Entries older than this period can be scheduled for auto-pruning to preserve disk space.
              </p>
            </div>

            <div style={{ marginTop: 18 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 6,
                  background: 'rgba(255, 255, 255, 0.04)',
                  padding: 3,
                  borderRadius: 8,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                {[
                  { sec: 604800, label: '7 Days' },
                  { sec: 1209600, label: '14 Days' },
                  { sec: 2592000, label: '30 Days' },
                ].map(item => {
                  const isActive = config.ttl_seconds === item.sec;
                  return (
                    <button
                      key={item.label}
                      onClick={() => handleSaveConfig({ ttl_seconds: item.sec })}
                      disabled={isSavingConfig}
                      style={{
                        padding: '6px 0',
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        fontFamily: 'var(--font-mono)',
                        textAlign: 'center',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? '#f59e0b' : 'transparent',
                        color: isActive ? '#ffffff' : '#a8a29e',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Card 5: Smart Agent Context Compactor */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Minimize2 size={16} color={config.compactor_enabled !== false ? '#34d399' : '#78716c'} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Context Compactor
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 12,
                    background: config.compactor_enabled !== false ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                    color: config.compactor_enabled !== false ? '#34d399' : '#78716c',
                    border: `1px solid ${config.compactor_enabled !== false ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
                  }}
                >
                  {config.compactor_enabled !== false ? 'ACTIVE' : 'OFF'}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                Prunes verbose tool execution outputs older than recent turns. Slashes 30k–100k token prompts by 50–70% while keeping system & recent turns 100% intact.
              </p>
            </div>

            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 6,
                  background: 'rgba(255, 255, 255, 0.04)',
                  padding: 3,
                  borderRadius: 8,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                {[
                  { window: 1, label: '1 turn' },
                  { window: 3, label: '3 turns (Safe)' },
                  { window: 5, label: '5 turns' },
                ].map(item => {
                  const isActive = (config.compactor_window ?? 3) === item.window;
                  return (
                    <button
                      key={item.label}
                      onClick={() => handleSaveConfig({ compactor_window: item.window })}
                      disabled={isSavingConfig}
                      style={{
                        padding: '6px 0',
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        fontFamily: 'var(--font-mono)',
                        textAlign: 'center',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? '#10b981' : 'transparent',
                        color: isActive ? '#ffffff' : '#a8a29e',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              <button
                onClick={() => handleSaveConfig({ compactor_enabled: config.compactor_enabled === false ? true : false })}
                disabled={isSavingConfig}
                className={`btn btn-sm ${config.compactor_enabled !== false ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '7px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  background: config.compactor_enabled !== false ? '#10b981' : undefined,
                  borderColor: config.compactor_enabled !== false ? '#10b981' : undefined,
                  color: '#ffffff',
                }}
              >
                {config.compactor_enabled !== false ? 'Compactor Enabled' : 'Compactor Disabled'}
              </button>
            </div>
          </div>

          {/* Card 6: AI Agent Runaway Loop Sentinel */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '18px 20px',
              borderRadius: 12,
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ShieldAlert size={16} color={config.loop_guard_enabled !== false ? '#f43f5e' : '#78716c'} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#ffffff' }}>
                    Runaway Loop Sentinel
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 12,
                    background: config.loop_guard_enabled !== false ? 'rgba(244, 63, 94, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                    color: config.loop_guard_enabled !== false ? '#f43f5e' : '#78716c',
                    border: `1px solid ${config.loop_guard_enabled !== false ? 'rgba(244, 63, 94, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
                  }}
                >
                  {config.loop_guard_enabled !== false ? 'GUARDING' : 'OFF'}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 10, lineHeight: 1.5 }}>
                Catches autonomous agents trapped in repetitive failing tool loops. Surgically injects corrective guidance to break infinite loops and stop quota drain.
              </p>
            </div>

            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 6,
                  background: 'rgba(255, 255, 255, 0.04)',
                  padding: 3,
                  borderRadius: 8,
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                {[
                  { repeat: 2, label: '2 calls' },
                  { repeat: 3, label: '3 calls (Strict)' },
                  { repeat: 5, label: '5 calls' },
                ].map(item => {
                  const isActive = (config.loop_guard_max_repeat ?? 3) === item.repeat;
                  return (
                    <button
                      key={item.label}
                      onClick={() => handleSaveConfig({ loop_guard_max_repeat: item.repeat })}
                      disabled={isSavingConfig}
                      style={{
                        padding: '6px 0',
                        fontSize: 11,
                        fontWeight: isActive ? 700 : 500,
                        fontFamily: 'var(--font-mono)',
                        textAlign: 'center',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? '#f43f5e' : 'transparent',
                        color: isActive ? '#ffffff' : '#a8a29e',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              <button
                onClick={() => handleSaveConfig({ loop_guard_enabled: config.loop_guard_enabled === false ? true : false })}
                disabled={isSavingConfig}
                className={`btn btn-sm ${config.loop_guard_enabled !== false ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  padding: '7px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  background: config.loop_guard_enabled !== false ? '#f43f5e' : undefined,
                  borderColor: config.loop_guard_enabled !== false ? '#f43f5e' : undefined,
                  color: '#ffffff',
                }}
              >
                {config.loop_guard_enabled !== false ? 'Loop Guard Active' : 'Loop Guard Disabled'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Cached Entries Table */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14, marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: '#ffffff' }}>
                Persistent Cache Ledger
              </h2>
              <span className="badge badge-emerald" style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                {totalEntriesCount} Patterns
              </span>
            </div>
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
                  const responseSnippet = entry.response_preview || entry.response_text || '(Empty Response)';
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
                            color: '#34d399',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 11,
                          }}
                          title={responseSnippet}
                        >
                          {responseSnippet}
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
