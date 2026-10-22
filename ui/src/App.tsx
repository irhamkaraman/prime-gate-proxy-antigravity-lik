import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ToastProvider, useToast } from './context/ToastContext';
import { ModalProvider, useModal } from './context/ModalContext';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ToastContainer } from './components/ToastContainer';
import { Modal } from './components/Modal';

import { DashboardPage } from './pages/DashboardPage';
import { ModelBenchmarkPage } from './pages/ModelBenchmarkPage';
import { CachingUsagePage } from './pages/CachingUsagePage';
import { AccountManagerPage } from './pages/AccountManagerPage';
import { PromptSandboxPage } from './pages/PromptSandboxPage';
import { SentinelPage } from './pages/SentinelPage';
import { DocumentationPage } from './pages/DocumentationPage';
import { ApiKeysPage } from './pages/ApiKeysPage';

import { Account, TelemetryMetrics, TokenVolumePoint, TimeRange } from './types';
import { ExternalLink, Copy, Check, KeyRound, Sparkles, Download } from 'lucide-react';

const initialMetrics: TelemetryMetrics = {
  throughput_tokens_per_sec: 0.0,
  tokens_today: {
    total: 0,
    prompt: 0,
    completion: 0,
    reasoning: 0,
  },
  latency_ms: {
    ttft_avg: 0,
    status: 'optimal',
  },
  cumulative: {
    requests: 0,
    tokens: 0,
  },
  active_subscribers: 1,
};

const MainLayout: React.FC = () => {
  const { currentRoute } = useNavigation();
  const { showToast } = useToast();
  const { openModal, closeModal } = useModal();

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [activeAccount, setActiveAccount] = useState<Account | null>(null);
  const [metrics, setMetrics] = useState<TelemetryMetrics>(initialMetrics);
  const [chartPoints, setChartPoints] = useState<TokenVolumePoint[]>([]);
  const [timeRange, setTimeRange] = useState<TimeRange>('1h');
  const timeRangeRef = useRef<TimeRange>('1h');
  const [isChartLoading, setIsChartLoading] = useState<boolean>(false);
  const [lastLedgerUpdate, setLastLedgerUpdate] = useState<number>(Date.now());
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [loginKey, setLoginKey] = useState<string>('');
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    timeRangeRef.current = timeRange;
  }, [timeRange]);
  // Check dashboard session authentication on mount
  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        const res = await fetch('/api/auth/session/status');
        if (res.ok) {
          const data = await res.json();
          setIsAuthenticated(!!data.authenticated);
        } else {
          setIsAuthenticated(false);
        }
      } catch {
        setIsAuthenticated(false);
      }
    };
    checkAuthStatus();

    const onAuthRequired = () => setIsAuthenticated(false);
    window.addEventListener('pg_auth_required', onAuthRequired);
    return () => window.removeEventListener('pg_auth_required', onAuthRequired);
  }, []);

  const handleLoginSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!loginKey.trim()) return;
    setIsLoggingIn(true);
    try {
      const res = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: loginKey.trim() })
      });
      if (res.ok) {
        setIsAuthenticated(true);
        setLoginKey('');
        showToast('Login berhasil! Sesi dashboard aktif.', 'success');
        fetchAccounts();
        fetchMetrics(timeRangeRef.current);
      } else {
        const err = await res.json();
        const msg = err.detail?.error?.message || err.detail || 'API Key tidak valid';
        showToast(msg, 'error');
      }
    } catch {
      showToast('Gagal menghubungi gateway server', 'error');
    } finally {
      setIsLoggingIn(false);
    }
  };


  // Fetch accounts list and real-time active account quota
  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch('/api/accounts');
      if (res.ok) {
        const data = await res.json();
        const list: Account[] = Array.isArray(data) ? data : data.accounts || [];
        setAccounts(list);
        let active = list.find(a => a.is_active) || (list.length > 0 ? list[0] : null);

        // Fetch live quota for the active account
        try {
          const qRes = await fetch('/api/quota');
          if (qRes.ok) {
            const qData = await qRes.json();
            if (qData.quota && Array.isArray(qData.quota)) {
              if (active) {
                active = { ...active, quota_summary: qData.quota, tier: qData.tier || active.tier };
              }
            }
          }
        } catch (e) {
          console.debug('Failed to fetch live quota in background:', e);
        }

        setActiveAccount(active);
      }
    } catch (err) {
      console.error('Failed to fetch accounts:', err);
    }
  }, []);

  // Fetch telemetry metrics and real-time time-series chart data
  const fetchMetrics = useCallback(async (rangeToFetch: TimeRange = '1h') => {
    try {
      const res = await fetch(`/api/metrics/tokens?range=${rangeToFetch}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.metrics) {
          setMetrics(data.metrics);
        } else if (data && data.summary) {
          const s = data.summary;
          setMetrics({
            throughput_tokens_per_sec: s.current_tokens_per_sec ?? 0.0,
            tokens_today: {
              total: s.tokens_today ?? s.total_tokens_all_time ?? 0,
              prompt: s.total_prompt_tokens ?? 0,
              completion: s.total_completion_tokens ?? 0,
              reasoning: s.total_reasoning_tokens ?? 0,
            },
            latency_ms: {
              ttft_avg: s.avg_latency_ms ?? 0.0,
              status: (s.avg_latency_ms ?? 0.0) < 4000 ? 'optimal' : 'warning',
            },
            cumulative: {
              requests: s.total_requests_all_time ?? 0,
              tokens: s.total_tokens_all_time ?? 0,
            },
            active_subscribers: 1,
          });
        }

        if (data && data.chart_data && Array.isArray(data.chart_data.labels)) {
          const pts: TokenVolumePoint[] = data.chart_data.labels.map((lbl: string, idx: number) => ({
            timestamp: String(idx),
            timeLabel: lbl,
            prompt: data.chart_data.prompt_tokens[idx] || 0,
            reasoning: data.chart_data.reasoning_tokens[idx] || 0,
            completion: data.chart_data.completion_tokens[idx] || 0,
            total: data.chart_data.total_tokens[idx] || 0,
          }));
          setChartPoints(pts);
        }
      }
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  }, []);

  // Force sync quota from Google Antigravity
  const handleSyncQuota = useCallback(async () => {
    setIsSyncing(true);
    try {
      const res = await fetch('/api/quota/sync', { method: 'POST' });
      if (!res.ok) throw new Error('Quota sync failed');
      const data = await res.json();
      showToast(data.message || 'Live quota & models synced with Google Antigravity!', 'success');
      if (data.quota && Array.isArray(data.quota)) {
        setActiveAccount(prev => prev ? { ...prev, quota_summary: data.quota } : null);
      }
      await fetchAccounts();
      await fetchMetrics(timeRange);
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to sync quota', 'error');
    } finally {
      setIsSyncing(false);
    }
  }, [fetchAccounts, fetchMetrics, showToast, timeRange]);

  // WebSocket Live Connection
  useEffect(() => {
    let reconnectTimeout: number;

    const connectWs = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Connect through Vite proxy or Node server
        const wsUrl = `${protocol}//${window.location.host}/ws/live`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const msgType = (data.type || '').toUpperCase();
            if (msgType === 'TELEMETRY_UPDATE') {
              setLastLedgerUpdate(Date.now());
              if (data.metrics) {
                setMetrics(prev => ({
                  ...prev,
                  throughput_tokens_per_sec: data.metrics.throughput_tokens_per_sec ?? prev.throughput_tokens_per_sec,
                  tokens_today: data.metrics.tokens_today ?? prev.tokens_today,
                  cumulative: data.metrics.cumulative ?? prev.cumulative,
                  latency_ms: data.metrics.latency_ms ?? prev.latency_ms,
                }));
              }
              // Only apply real-time chart points directly if client is currently on 1h (default)!
              if (timeRangeRef.current === '1h') {
                if (data.chart_data && Array.isArray(data.chart_data.labels)) {
                  const pts: TokenVolumePoint[] = data.chart_data.labels.map((lbl: string, idx: number) => ({
                    timestamp: String(idx),
                    timeLabel: lbl,
                    prompt: data.chart_data.prompt_tokens[idx] || 0,
                    reasoning: data.chart_data.reasoning_tokens[idx] || 0,
                    completion: data.chart_data.completion_tokens[idx] || 0,
                    total: data.chart_data.total_tokens[idx] || 0,
                  }));
                  setChartPoints(pts);
                }
              } else {
                // If viewing 1h, 1d, or 1month, re-fetch for active range so it never reverts to 1m
                fetchMetrics(timeRangeRef.current);
              }
            } else if (
              msgType === 'REQUEST_LOGGED' ||
              msgType === 'LEDGER_CLEARED' ||
              msgType === 'CACHE_HIT' ||
              msgType === 'CACHE_STORED' ||
              msgType === 'CACHE_CLEARED' ||
              msgType === 'CACHE_CONFIG_UPDATED' ||
              msgType === 'AUTO_UPDATE_CONFIG_UPDATED'
            ) {
              setLastLedgerUpdate(Date.now());
            } else if (msgType === 'AUTO_UPDATE_COMPLETED' || msgType === 'SYSTEM_UPDATE_COMPLETED') {
              showToast(`System updated to commit #${data.commit || ''}! Refreshing page...`, 'success');
              setTimeout(() => {
                window.location.reload();
              }, 2000);
            } else if (msgType === 'ACCOUNT_SWITCHED') {
              if (data.quota && Array.isArray(data.quota) && data.quota.length > 0) {
                setActiveAccount(prev => prev ? { ...prev, email: data.email || prev.email, quota_summary: data.quota } : null);
              }
              fetchAccounts();
              fetchMetrics(timeRangeRef.current);
            } else if (msgType === 'QUOTA_UPDATE' || msgType === 'QUOTA_UPDATED' || msgType === 'ACCOUNT_CONNECTED' || msgType === 'ACCOUNT_REMOVED') {
              fetchAccounts();
            }
          } catch (e) {
            // ignore non-json messages
          }
        };

        ws.onclose = () => {
          setIsWsConnected(false);
          reconnectTimeout = window.setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          setIsWsConnected(false);
          ws.close();
        };
      } catch (err) {
        setIsWsConnected(false);
        reconnectTimeout = window.setTimeout(connectWs, 3000);
      }
    };

    connectWs();
    fetchAccounts();
    fetchMetrics('1h');

    const pollingInterval = setInterval(() => {
      fetchMetrics(timeRange);
    }, 4000);

    return () => {
      clearInterval(pollingInterval);
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [fetchAccounts, fetchMetrics, timeRange]);

  // Open "Add Account" Modal with Google OAuth flow & JSON import
  const handleOpenAddAccountModal = () => {
    let pollInterval: number;
    const startOAuth = async () => {
      try {
        const urlRes = await fetch('/api/auth/url');
        if (urlRes.ok) {
          const urlData = await urlRes.json();
          if (urlData.auth_url) {
            window.open(urlData.auth_url, '_blank');
            showToast('Google OAuth window opened. Please approve access.', 'info');
          }
        }
        fetch('/api/auth/login', { method: 'POST' })
          .then(res => res.json())
          .then(data => {
            if (data.success) {
              showToast(`Account ${data.account} successfully connected!`, 'success');
              fetchAccounts();
              closeModal();
            } else if (data.error) {
              showToast(data.error, 'error');
            }
          })
          .catch(e => {
            console.error('OAuth background login error:', e);
          });
      } catch (e) {
        console.error('Failed to trigger OAuth login:', e);
        showToast('Failed to start Google sign-in process', 'error');
      }
    };

    const handleImportOpenCode = async () => {
      try {
        showToast('Scanning OpenCode configuration for accounts...', 'info');
        const res = await fetch('/api/auth/import', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          if (data.success) {
            showToast(`Imported ${data.imported} account(s) from OpenCode!`, 'success');
            await fetchAccounts();
            closeModal();
          } else {
            showToast('No new OpenCode accounts found to import.', 'info');
          }
        } else {
          showToast('Failed to import OpenCode accounts', 'error');
        }
      } catch (e) {
        showToast('Failed to connect to backend for import', 'error');
      }
    };

    openModal({
      title: 'Connect Google Antigravity Account',
      description: 'Authenticate an account to balance quotas and enable model routing.',
      cancelText: 'Cancel',
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* OAuth Option */}
          <div
            style={{
              padding: 20,
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Sparkles size={20} color="#f59e0b" />
              <div>
                <h4 style={{ fontSize: 14, fontWeight: 700, color: '#ffffff' }}>
                  1-Click Interactive Google OAuth
                </h4>
                <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
                  Opens browser tab to sign in via Google. Prime Gate captures tokens automatically on port 53123.
                </p>
              </div>
            </div>

            <button
              onClick={startOAuth}
              className="btn btn-primary"
              style={{ width: '100%', padding: '12px 16px' }}
            >
              <ExternalLink size={15} />
              <span>Launch Google Sign-In</span>
            </button>
          </div>

          {/* OpenCode Import Option */}
          <div
            style={{
              padding: 18,
              borderRadius: 12,
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Download size={18} color="#d6d3d1" />
              <div>
                <h4 style={{ fontSize: 13, fontWeight: 600, color: '#ffffff' }}>
                  Import from OpenCode
                </h4>
                <p style={{ fontSize: 12, color: '#78716c', marginTop: 2 }}>
                  Auto-sync existing accounts from local OpenCode JSON configuration.
                </p>
              </div>
            </div>

            <button
              onClick={handleImportOpenCode}
              className="btn btn-secondary"
              style={{ width: '100%', padding: '10px 14px' }}
            >
              <Download size={14} />
              <span>Import Configured Accounts</span>
            </button>
          </div>

          {/* Polling notice */}
          <div style={{ fontSize: 12, color: '#78716c', textAlign: 'center' }}>
            Listening for authentication callback... This modal will auto-refresh once signed in.
          </div>
        </div>
      ),
      onCancel: () => {
        clearInterval(pollInterval);
      },
    });

    // Poll for account appearance
    const prevCount = accounts.length;
    pollInterval = window.setInterval(async () => {
      try {
        const res = await fetch('/api/accounts');
        if (res.ok) {
          const data = await res.json();
          const list: Account[] = Array.isArray(data) ? data : data.accounts || [];
          if (list.length > prevCount) {
            clearInterval(pollInterval);
            setAccounts(list);
            const newest = list[list.length - 1];
            setActiveAccount(newest);
            closeModal();
            showToast(`Connected account ${newest.email} successfully!`, 'success');
          }
        }
      } catch (err) {
        // ignore polling err
      }
    }, 2000);
  };


  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0d14', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <div style={{
          width: '100%',
          maxWidth: 440,
          padding: 32,
          borderRadius: 20,
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(56, 189, 248, 0.1)',
          backdropFilter: 'blur(20px)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #0ea5e9, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 24px rgba(14, 165, 233, 0.4)'
            }}>
              <KeyRound size={28} color="#ffffff" />
            </div>
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, textAlign: 'center', color: '#f8fafc', marginBottom: 8 }}>
            Prime Gate Gateway
          </h2>
          <p style={{ fontSize: 13, textAlign: 'center', color: '#94a3b8', marginBottom: 24, lineHeight: 1.5 }}>
            Dashboard ini dilindungi enkripsi AES-256-GCM. Masukkan API Key Anda untuk membuka sesi aman.
          </p>
          <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                API Key (Bearer Secret)
              </label>
              <input
                type="password"
                value={loginKey}
                onChange={e => setLoginKey(e.target.value)}
                placeholder="pg-live-..."
                autoFocus
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: 12,
                  background: 'rgba(2, 6, 23, 0.7)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  color: '#ffffff',
                  fontSize: 14,
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn || !loginKey.trim()}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #0ea5e9, #2563eb)',
                color: '#ffffff',
                fontWeight: 600,
                fontSize: 14,
                border: 'none',
                cursor: (isLoggingIn || !loginKey.trim()) ? 'not-allowed' : 'pointer',
                opacity: (isLoggingIn || !loginKey.trim()) ? 0.6 : 1,
                boxShadow: '0 4px 14px rgba(14, 165, 233, 0.3)',
                transition: 'all 0.2s'
              }}
            >
              {isLoggingIn ? 'Memverifikasi...' : 'Masuk ke Dashboard'}
            </button>
          </form>
          <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid rgba(148, 163, 184, 0.1)', textAlign: 'center' }}>
            <span style={{ fontSize: 12, color: '#64748b' }}>
              Belum punya key? Buat via CLI:{' '}
              <code style={{ color: '#38bdf8', background: 'rgba(15, 23, 42, 0.8)', padding: '2px 6px', borderRadius: 4 }}>
                prime-gate auth create-key
              </code>
            </span>
          </div>
        </div>
        <ToastContainer />
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <Sidebar
        activeAccount={activeAccount}
        accounts={accounts}
        onAccountSwitched={fetchAccounts}
        isWsConnected={isWsConnected}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header
          onSyncQuota={handleSyncQuota}
          onOpenAddAccountModal={handleOpenAddAccountModal}
          isSyncing={isSyncing}
        />

        {/* Dynamic Route Render */}
        <main style={{ flex: 1 }}>
          {currentRoute === 'dashboard' && (
            <DashboardPage
              metrics={metrics}
              activeAccount={activeAccount}
              chartPoints={chartPoints}
              timeRange={timeRange}
              isChartLoading={isChartLoading}
              onTimeRangeChange={async (newRange) => {
                if (newRange === timeRangeRef.current && chartPoints.length > 0) return;
                setTimeRange(newRange);
                timeRangeRef.current = newRange;
                setIsChartLoading(true);
                const startTime = Date.now();
                try {
                  await fetchMetrics(newRange);
                } finally {
                  const elapsed = Date.now() - startTime;
                  const remaining = Math.max(0, 300 - elapsed);
                  setTimeout(() => {
                    setIsChartLoading(false);
                  }, remaining);
                }
              }}
              onSyncQuota={handleSyncQuota}
              isSyncing={isSyncing}
              lastLedgerUpdate={lastLedgerUpdate}
            />
          )}

          {currentRoute === 'benchmarks' && (
            <ModelBenchmarkPage
              activeAccount={activeAccount}
              lastLedgerUpdate={lastLedgerUpdate}
              isWsConnected={isWsConnected}
            />
          )}

          {currentRoute === 'caching' && (
            <CachingUsagePage
              lastLedgerUpdate={lastLedgerUpdate}
              isWsConnected={isWsConnected}
            />
          )}

          {currentRoute === 'accounts' && (
            <AccountManagerPage
              accounts={accounts}
              activeAccount={activeAccount}
              onRefresh={fetchAccounts}
              onOpenAddModal={handleOpenAddAccountModal}
            />
          )}

          {currentRoute === 'sandbox' && <PromptSandboxPage />}

          {currentRoute === 'keys' && <ApiKeysPage />}

          {currentRoute === 'sentinel' && <SentinelPage />}

          {currentRoute === 'docs' && <DocumentationPage />}
        </main>
      </div>

      {/* Global Notifications and Modals */}
      <ToastContainer />
      <Modal />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <ModalProvider>
        <NavigationProvider>
          <MainLayout />
        </NavigationProvider>
      </ModalProvider>
    </ToastProvider>
  );
};
