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
import { AccountManagerPage } from './pages/AccountManagerPage';
import { PromptSandboxPage } from './pages/PromptSandboxPage';
import { SentinelPage } from './pages/SentinelPage';
import { DocumentationPage } from './pages/DocumentationPage';

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
  const [timeRange, setTimeRange] = useState<TimeRange>('1m');
  const timeRangeRef = useRef<TimeRange>('1m');
  const [lastLedgerUpdate, setLastLedgerUpdate] = useState<number>(Date.now());
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    timeRangeRef.current = timeRange;
  }, [timeRange]);

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
  const fetchMetrics = useCallback(async (rangeToFetch: TimeRange = '1m') => {
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
              // Only apply real-time chart points directly if client is currently on 1m!
              if (timeRangeRef.current === '1m') {
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
            } else if (msgType === 'REQUEST_LOGGED' || msgType === 'LEDGER_CLEARED') {
              setLastLedgerUpdate(Date.now());
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
    fetchMetrics('1m');

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
              onTimeRangeChange={(newRange) => {
                setTimeRange(newRange);
                timeRangeRef.current = newRange;
                fetchMetrics(newRange);
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

          {currentRoute === 'accounts' && (
            <AccountManagerPage
              accounts={accounts}
              activeAccount={activeAccount}
              onRefresh={fetchAccounts}
              onOpenAddModal={handleOpenAddAccountModal}
            />
          )}

          {currentRoute === 'sandbox' && <PromptSandboxPage />}

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
