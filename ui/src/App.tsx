import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ToastProvider, useToast } from './context/ToastContext';
import { ModalProvider, useModal } from './context/ModalContext';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ToastContainer } from './components/ToastContainer';
import { Modal } from './components/Modal';

import { DashboardPage } from './pages/DashboardPage';
import { AccountManagerPage } from './pages/AccountManagerPage';
import { PromptSandboxPage } from './pages/PromptSandboxPage';
import { SentinelPage } from './pages/SentinelPage';
import { DocumentationPage } from './pages/DocumentationPage';

import { Account, TelemetryMetrics } from './types';
import { ExternalLink, Copy, Check, KeyRound, Sparkles } from 'lucide-react';

const initialMetrics: TelemetryMetrics = {
  throughput_tokens_per_sec: 0.0,
  tokens_today: {
    total: 96352,
    prompt: 94901,
    completion: 366,
    reasoning: 1085,
  },
  latency_ms: {
    ttft_avg: 3121,
    status: 'optimal',
  },
  cumulative: {
    requests: 21,
    tokens: 96352,
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
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch accounts list
  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch('/api/accounts');
      if (res.ok) {
        const data = await res.json();
        const list: Account[] = Array.isArray(data) ? data : data.accounts || [];
        setAccounts(list);
        const active = list.find(a => a.is_active) || (list.length > 0 ? list[0] : null);
        setActiveAccount(active);
      }
    } catch (err) {
      console.error('Failed to fetch accounts:', err);
    }
  }, []);

  // Fetch telemetry metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch('/api/metrics/tokens?range=minute');
      if (res.ok) {
        const data = await res.json();
        if (data && data.metrics) {
          setMetrics(prev => ({
            ...prev,
            throughput_tokens_per_sec: data.metrics.throughput_tokens_per_sec ?? prev.throughput_tokens_per_sec,
            tokens_today: data.metrics.tokens_today ?? prev.tokens_today,
            cumulative: data.metrics.cumulative ?? prev.cumulative,
          }));
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
      await fetchAccounts();
      await fetchMetrics();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to sync quota', 'error');
    } finally {
      setIsSyncing(false);
    }
  }, [fetchAccounts, fetchMetrics, showToast]);

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
            if (data.type === 'telemetry_update' && data.metrics) {
              setMetrics(prev => ({
                ...prev,
                throughput_tokens_per_sec: data.metrics.throughput ?? prev.throughput_tokens_per_sec,
                tokens_today: data.metrics.tokens_today ?? prev.tokens_today,
              }));
            } else if (data.type === 'quota_update') {
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
    fetchMetrics();

    const pollingInterval = setInterval(() => {
      fetchMetrics();
    }, 5000);

    return () => {
      clearInterval(pollingInterval);
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [fetchAccounts, fetchMetrics]);

  // Open "Add Account" Modal with Google OAuth flow & JSON import
  const handleOpenAddAccountModal = () => {
    let pollInterval: number;
    let authUrl = '';

    const startOAuth = async () => {
      try {
        const res = await fetch('/api/auth/login', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          authUrl = data.auth_url || '';
          if (authUrl) {
            window.open(authUrl, '_blank');
            showToast('Google OAuth window opened. Please approve access.', 'info');
          }
        }
      } catch (e) {
        console.error('Failed to trigger OAuth login:', e);
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

          {/* Polling notice */}
          <div style={{ fontSize: 12, color: '#78716c', textAlign: 'center' }}>
            Listening for Google authentication callback... This modal will auto-refresh once signed in.
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
              onSyncQuota={handleSyncQuota}
              isSyncing={isSyncing}
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
