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
import { ExternalLink, Copy, Check, KeyRound, Sparkles, Download, Eye, EyeOff, ArrowRight, RefreshCw, ShieldCheck, Zap } from 'lucide-react';

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
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [copiedCliCmd, setCopiedCliCmd] = useState<boolean>(false);
  const [isInputFocused, setIsInputFocused] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    timeRangeRef.current = timeRange;
  }, [timeRange]);

  // Close mobile sidebar on route change
  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [currentRoute]);
  // Check dashboard session authentication on mount
  useEffect(() => {
    const checkAuthStatus = async (retryCount = 0) => {
      // 1. Verify if session cookie is already active
      try {
        const res = await fetch('/api/auth/session/status');
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            setIsAuthenticated(true);
            return;
          }
        } else if (res.status === 502 || res.status === 503) {
          // Backend is booting up. Retry smoothly without destroying local state
          if (retryCount < 3) {
            setTimeout(() => checkAuthStatus(retryCount + 1), 1000);
            return;
          }
        }
      } catch {
        if (retryCount < 3) {
          setTimeout(() => checkAuthStatus(retryCount + 1), 1000);
          return;
        }
      }

      // 2. Client-side persistent storage auto-login
      const savedKey = localStorage.getItem('pg_dashboard_api_key');
      if (savedKey) {
        try {
          const loginRes = await fetch('/api/auth/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: savedKey.trim() })
          });
          if (loginRes.ok) {
            setIsAuthenticated(true);
            return;
          } else if (loginRes.status === 401) {
            // ONLY remove key if explicitly rejected as invalid, not on 502/network timeouts
            localStorage.removeItem('pg_dashboard_api_key');
          }
        } catch (e) {
          console.debug('Auto-login fallback failed:', e);
        }
      }

      // 3. Loopback Fallback: Automatically establish session for local machine owner (127.0.0.1)
      try {
        const localLoginRes = await fetch('/api/auth/session/local-login', {
          method: 'POST'
        });
        if (localLoginRes.ok) {
          setIsAuthenticated(true);
          return;
        }
      } catch (e) {
        console.debug('Local loopback auto-login deferred:', e);
      }

      setIsAuthenticated(false);
    };
    checkAuthStatus();

    const onAuthRequired = async () => {
      const savedKey = localStorage.getItem('pg_dashboard_api_key');
      if (savedKey) {
        try {
          const loginRes = await fetch('/api/auth/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: savedKey.trim() })
          });
          if (loginRes.ok) {
            setIsAuthenticated(true);
            return;
          } else if (loginRes.status === 401) {
            localStorage.removeItem('pg_dashboard_api_key');
          }
        } catch {
          // ignore transient network failure
        }
      }

      // Attempt loopback session before showing modal
      try {
        const localLoginRes = await fetch('/api/auth/session/local-login', {
          method: 'POST'
        });
        if (localLoginRes.ok) {
          setIsAuthenticated(true);
          return;
        }
      } catch {
        // ignore
      }

      setIsAuthenticated(false);
    };

    window.addEventListener('pg_auth_required', onAuthRequired);
    return () => window.removeEventListener('pg_auth_required', onAuthRequired);
  }, []);

  const handleLoginSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const keyToUse = loginKey.trim();
    if (!keyToUse) return;
    setIsLoggingIn(true);
    try {
      const res = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: keyToUse })
      });
      if (res.ok) {
        // Persist key locally so the user never has to re-generate or re-enter key
        localStorage.setItem('pg_dashboard_api_key', keyToUse);
        setIsAuthenticated(true);
        setLoginKey('');
        showToast('Login berhasil! Sesi dashboard aktif permanen.', 'success');
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

  const handleLocalAutoLogin = async () => {
    setIsLoggingIn(true);
    try {
      const res = await fetch('/api/auth/session/local-login', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(true);
        showToast(`Sesi aktif otomatis untuk ${data.key_name || 'Local Machine'}!`, 'success');
        fetchAccounts();
        fetchMetrics(timeRangeRef.current);
      } else {
        const err = await res.json().catch(() => ({}));
        const msg = err.detail?.error?.message || err.detail || 'Auto-login loopback tidak dapat digunakan.';
        showToast(msg, 'error');
      }
    } catch {
      showToast('Gagal menghubungi gateway server (port 52111 unreachable)', 'error');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/session/logout', { method: 'POST' });
    } catch (e) {
      console.debug('Logout request failed:', e);
    }
    localStorage.removeItem('pg_dashboard_api_key');
    setIsAuthenticated(false);
    showToast('Sesi dashboard telah ditutup.', 'info');
  };

  const handleCopyCliCmd = () => {
    navigator.clipboard.writeText('prime-gate auth create-key').then(() => {
      setCopiedCliCmd(true);
      showToast('Perintah CLI berhasil disalin!', 'success');
      setTimeout(() => setCopiedCliCmd(false), 2000);
    });
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
      <div
        style={{
          minHeight: '100vh',
          background: `
            radial-gradient(ellipse 65% 50% at 50% -10%, rgba(245, 158, 11, 0.12), transparent 75%),
            radial-gradient(circle 420px at 50% 100%, rgba(217, 119, 6, 0.08), transparent 70%),
            radial-gradient(circle 600px at 15% 50%, rgba(245, 158, 11, 0.03), transparent 60%),
            radial-gradient(circle 600px at 85% 50%, rgba(217, 119, 6, 0.03), transparent 60%),
            #090807
          `,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          fontFamily: 'var(--font-sans)',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        {/* Subtle Cyber-Grid Background Accent */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `
              linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px)
            `,
            backgroundSize: '36px 36px',
            pointerEvents: 'none',
          }}
        />

        {/* Login Card */}
        <div
          className="animate-fade-in"
          style={{
            width: '100%',
            maxWidth: 440,
            padding: '36px 32px 30px',
            borderRadius: 20,
            background: 'linear-gradient(180deg, #15110e 0%, #100c09 100%)',
            border: '1px solid rgba(168, 162, 158, 0.18)',
            boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.9), 0 0 40px rgba(245, 158, 11, 0.06)',
            backdropFilter: 'blur(20px)',
            position: 'relative',
            zIndex: 10
          }}
        >
          {/* Top Amber Shimmer Strip */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 36,
              right: 36,
              height: 2,
              background: 'linear-gradient(90deg, transparent, #f59e0b, #d97706, transparent)',
              borderRadius: 999
            }}
          />

          {/* Brand Logo & Halo */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
            <div
              style={{
                width: 62,
                height: 62,
                borderRadius: 18,
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 24px rgba(245, 158, 11, 0.22)'
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 14,
                  background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 4px 14px rgba(217, 119, 6, 0.45)'
                }}
              >
                <KeyRound size={24} color="#ffffff" />
              </div>
            </div>
          </div>

          {/* Title & Version Badge */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 8 }}>
            <h2
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: '#fafaf9',
                letterSpacing: '-0.02em',
                margin: 0
              }}
            >
              Prime Gate Gateway
            </h2>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#f59e0b',
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                padding: '2px 7px',
                borderRadius: 5,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.02em'
              }}
            >
              v1.2.4
            </span>
          </div>

          {/* Subtitle */}
          <p
            style={{
              fontSize: 13,
              textAlign: 'center',
              color: '#a8a29e',
              lineHeight: 1.5,
              marginBottom: 16
            }}
          >
            Dashboard ini dilindungi enkripsi <strong style={{ color: '#fafaf9' }}>AES-256-GCM</strong>. Masukkan API Key Anda untuk membuka sesi aman.
          </p>

          {/* Security Status Pill */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                padding: '4px 12px',
                borderRadius: 999,
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.22)',
                color: '#34d399',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.02em'
              }}
            >
              <span className="pulse-dot" style={{ width: 6, height: 6 }} />
              <span>Hardware-Accelerated Vault Protected</span>
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#a8a29e',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em'
                  }}
                >
                  API Key (Bearer Secret)
                </label>
                <span
                  style={{
                    fontSize: 10,
                    color: '#78716c',
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  Header: Bearer
                </span>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: '#090807',
                  border: isInputFocused ? '1px solid #f59e0b' : '1px solid rgba(168, 162, 158, 0.22)',
                  borderRadius: 12,
                  padding: '0 12px 0 14px',
                  boxShadow: isInputFocused ? '0 0 0 3px rgba(245, 158, 11, 0.18)' : 'inset 0 1px 2px rgba(0, 0, 0, 0.5)',
                  transition: 'all 0.2s ease'
                }}
              >
                <KeyRound
                  size={16}
                  color={isInputFocused ? '#f59e0b' : '#78716c'}
                  style={{ flexShrink: 0, marginRight: 10, transition: 'color 0.2s' }}
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={loginKey}
                  onChange={e => setLoginKey(e.target.value)}
                  onFocus={() => setIsInputFocused(true)}
                  onBlur={() => setIsInputFocused(false)}
                  placeholder="pg-live-..."
                  autoFocus
                  style={{
                    flex: 1,
                    padding: '12px 0',
                    background: 'transparent',
                    border: 'none',
                    color: '#fafaf9',
                    fontSize: 13.5,
                    fontFamily: 'var(--font-mono)',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
                {loginKey && (
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#78716c',
                      cursor: 'pointer',
                      padding: 4,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: 6,
                      transition: 'color 0.2s'
                    }}
                    title={showPassword ? 'Sembunyikan Key' : 'Tampilkan Key'}
                    onMouseEnter={e => (e.currentTarget.style.color = '#fafaf9')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#78716c')}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoggingIn || !loginKey.trim()}
              style={{
                width: '100%',
                padding: '12px 18px',
                borderRadius: 12,
                background: (isLoggingIn || !loginKey.trim())
                  ? 'rgba(217, 119, 6, 0.3)'
                  : 'linear-gradient(135deg, #d97706, #b45309)',
                color: '#ffffff',
                fontWeight: 700,
                fontSize: 14,
                fontFamily: 'var(--font-sans)',
                border: 'none',
                cursor: (isLoggingIn || !loginKey.trim()) ? 'not-allowed' : 'pointer',
                opacity: (isLoggingIn || !loginKey.trim()) ? 0.65 : 1,
                boxShadow: (isLoggingIn || !loginKey.trim()) ? 'none' : '0 4px 16px rgba(217, 119, 6, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                transition: 'all 0.2s ease',
                letterSpacing: '-0.01em'
              }}
              onMouseEnter={e => {
                if (!isLoggingIn && loginKey.trim()) {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 6px 20px rgba(217, 119, 6, 0.45)';
                }
              }}
              onMouseLeave={e => {
                if (!isLoggingIn && loginKey.trim()) {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #d97706, #b45309)';
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(217, 119, 6, 0.35)';
                }
              }}
            >
              {isLoggingIn ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  <span>Memverifikasi Sesi...</span>
                </>
              ) : (
                <>
                  <span>Masuk ke Dashboard</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {/* Quick Auto-Connect for Local Host */}
            <button
              type="button"
              onClick={handleLocalAutoLogin}
              disabled={isLoggingIn}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 12,
                background: 'rgba(245, 158, 11, 0.06)',
                border: '1px solid rgba(245, 158, 11, 0.22)',
                color: '#fbbf24',
                fontSize: 12.5,
                fontWeight: 600,
                fontFamily: 'var(--font-sans)',
                cursor: isLoggingIn ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                transition: 'all 0.2s ease',
                marginTop: -4
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(245, 158, 11, 0.14)';
                e.currentTarget.style.borderColor = '#f59e0b';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(245, 158, 11, 0.06)';
                e.currentTarget.style.borderColor = 'rgba(245, 158, 11, 0.22)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <Zap size={14} color="#f59e0b" />
              <span>Auto-Detect & Masuk Otomatis (Local Machine)</span>
            </button>
          </form>

          {/* Footer CLI helper box */}
          <div
            style={{
              marginTop: 24,
              paddingTop: 18,
              borderTop: '1px solid rgba(255, 255, 255, 0.06)',
              textAlign: 'center'
            }}
          >
            <div style={{ fontSize: 12, color: '#78716c', marginBottom: 10 }}>
              Belum punya API key? Buat via CLI:
            </div>
            <div
              onClick={handleCopyCliCmd}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 12px',
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.22)',
                color: '#fbbf24',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                userSelect: 'none'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(245, 158, 11, 0.15)';
                e.currentTarget.style.borderColor = 'rgba(245, 158, 11, 0.4)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(245, 158, 11, 0.08)';
                e.currentTarget.style.borderColor = 'rgba(245, 158, 11, 0.22)';
              }}
              title="Klik untuk menyalin perintah CLI"
            >
              <span>prime-gate auth create-key</span>
              {copiedCliCmd ? <Check size={13} color="#10b981" /> : <Copy size={13} color="#f59e0b" />}
            </div>
          </div>
        </div>

        {/* Global Toast Notifications */}
        <ToastContainer />
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Mobile Backdrop */}
      {isMobileSidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Left Sidebar */}
      <Sidebar
        activeAccount={activeAccount}
        accounts={accounts}
        onAccountSwitched={fetchAccounts}
        isWsConnected={isWsConnected}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header
          onSyncQuota={handleSyncQuota}
          onOpenAddAccountModal={handleOpenAddAccountModal}
          isSyncing={isSyncing}
          isMobileSidebarOpen={isMobileSidebarOpen}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(prev => !prev)}
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
