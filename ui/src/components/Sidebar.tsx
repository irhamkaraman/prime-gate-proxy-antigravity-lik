import React, { useState, useEffect } from 'react';
import { useNavigation } from '../context/NavigationContext';
import { useModal } from '../context/ModalContext';
import { useToast } from '../context/ToastContext';
import {
  Activity,
  BarChart3,
  Zap,
  Users,
  Terminal,
  ShieldCheck,
  BookOpen,
  ArrowRightLeft,
  ChevronRight,
  RefreshCw,
  Download,
  AlertCircle,
  GitBranch,
} from 'lucide-react';
import { Account, RoutePath, SystemUpdateStatus, GitPullResponse } from '../types';

interface SidebarProps {
  activeAccount: Account | null;
  accounts: Account[];
  onAccountSwitched: () => void;
  isWsConnected: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeAccount,
  accounts,
  onAccountSwitched,
  isWsConnected,
}) => {
  const { currentRoute, navigate } = useNavigation();
  const { openModal, closeModal } = useModal();
  const { showToast } = useToast();
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null);

  const [updateInfo, setUpdateInfo] = useState<SystemUpdateStatus | null>(null);
  const [isPulling, setIsPulling] = useState(false);
  const [isTogglingAutoUpdate, setIsTogglingAutoUpdate] = useState(false);

  const fetchUpdateStatus = async () => {
    try {
      const res = await fetch('/api/system/update-status');
      if (res.ok) {
        const data: SystemUpdateStatus = await res.json();
        setUpdateInfo(data);
      }
    } catch (e) {
      console.warn('Failed to check system update status:', e);
    }
  };

  useEffect(() => {
    fetchUpdateStatus();
    const interval = setInterval(() => {
      fetchUpdateStatus();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleGitPull = async () => {
    if (isPulling) return;
    setIsPulling(true);
    showToast('Pulling latest updates from GitHub repository...', 'info');
    try {
      const res = await fetch('/api/system/git-pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data: GitPullResponse = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || data.message || 'Failed to execute git pull');
      }

      showToast(
        data.ui_rebuilt
          ? 'Update pulled and UI rebuilt successfully! Reloading system...'
          : 'Update pulled successfully! Reloading page...',
        'success'
      );

      if (data.status) {
        setUpdateInfo(data.status);
      }

      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to update repository', 'error');
    } finally {
      setIsPulling(false);
    }
  };

  const handleToggleAutoUpdate = async () => {
    const currentEnabled = updateInfo?.auto_update ? updateInfo.auto_update.enabled : true;
    const nextEnabled = !currentEnabled;
    setIsTogglingAutoUpdate(true);
    try {
      const res = await fetch('/api/system/auto-update/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextEnabled }),
      });
      if (res.ok) {
        const data = await res.json();
        setUpdateInfo(prev => prev ? {
          ...prev,
          auto_update: data.config
        } : null);
        showToast(
          nextEnabled
            ? 'Auto Update enabled! Updates will pull automatically when system is idle.'
            : 'Auto Update disabled.',
          'success'
        );
      }
    } catch {
      showToast('Failed to update Auto Update setting', 'error');
    } finally {
      setIsTogglingAutoUpdate(false);
    }
  };

  const navItems: Array<{
    id: RoutePath;
    label: string;
    icon: React.ReactNode;
  }> = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <Activity size={18} />,
    },
    {
      id: 'benchmarks',
      label: 'Usage',
      icon: <BarChart3 size={18} />,
    },
    {
      id: 'caching',
      label: 'Caching Usage',
      icon: <Zap size={18} />,
    },
    {
      id: 'accounts',
      label: 'Account Manager',
      icon: <Users size={18} />,
    },
    {
      id: 'sandbox',
      label: 'Prompt Sandbox',
      icon: <Terminal size={18} />,
    },
    {
      id: 'sentinel',
      label: 'System & Sentinel',
      icon: <ShieldCheck size={18} />,
    },
    {
      id: 'docs',
      label: 'Documentation',
      icon: <BookOpen size={18} />,
    },
  ];

  const handleSwitchAccount = async (email: string) => {
    try {
      setSwitchingEmail(email);
      const res = await fetch(`/api/accounts/switch?email=${encodeURIComponent(email)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        throw new Error('Failed to switch active account');
      }
      showToast(`Switched active account to ${email}`, 'success');
      onAccountSwitched();
      closeModal();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to switch account', 'error');
    } finally {
      setSwitchingEmail(null);
    }
  };

  const openSwitchAccountModal = () => {
    openModal({
      title: 'Switch Active Account',
      description: 'Select an account to route OpenAI requests through Google Antigravity:',
      cancelText: 'Close',
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          {accounts.map(acc => {
            const isActive = acc.email === activeAccount?.email;
            return (
              <div
                key={acc.email}
                onClick={() => !isActive && handleSwitchAccount(acc.email)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  borderRadius: 10,
                  background: isActive ? 'rgba(245, 158, 11, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                  border: `1px solid ${isActive ? 'rgba(245, 158, 11, 0.35)' : 'rgba(255, 255, 255, 0.08)'}`,
                  cursor: isActive ? 'default' : 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: isActive ? '#fbbf24' : '#fafaf9' }}>
                    {acc.email}
                  </div>
                  <div style={{ fontSize: 11, color: '#78716c', marginTop: 2 }}>
                    Tier: {acc.tier || 'Antigravity Pro'} &bull; {acc.models_count || 14} Models
                  </div>
                </div>
                {isActive ? (
                  <span className="badge badge-amber">Active</span>
                ) : (
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={switchingEmail === acc.email}
                  >
                    {switchingEmail === acc.email ? 'Switching...' : 'Select'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ),
    });
  };

  return (
    <aside
      style={{
        width: 260,
        height: '100vh',
        background: '#0d0a08',
        borderRight: '1px solid rgba(168, 162, 158, 0.14)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '20px 18px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 16, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
            Prime Gate
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: '#f59e0b',
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              padding: '2px 7px',
              borderRadius: 5,
              fontFamily: 'monospace',
              letterSpacing: '0.02em',
            }}
            title={`Version: v${updateInfo?.current_version || '1.2.3'}`}
          >
            v{updateInfo?.current_version || '1.2.3'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 11, color: '#78716c', fontWeight: 500 }}>
            Antigravity Gateway
          </div>
          {updateInfo?.current_commit && (
            <div
              style={{
                fontSize: 10,
                color: '#57534e',
                fontFamily: 'monospace',
              }}
              title={`Local Commit: ${updateInfo.current_commit}`}
            >
              #{updateInfo.current_commit}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
          <span style={{ fontSize: 11, color: '#a8a29e', fontWeight: 500 }}>
            Auto Update
          </span>
          <button
            onClick={handleToggleAutoUpdate}
            disabled={isTogglingAutoUpdate}
            type="button"
            role="switch"
            aria-checked={Boolean(updateInfo?.auto_update?.enabled)}
            style={{
              width: 30,
              height: 16,
              borderRadius: 999,
              background: updateInfo?.auto_update?.enabled ? '#10b981' : '#3f3f46',
              border: 'none',
              padding: 2,
              display: 'flex',
              alignItems: 'center',
              cursor: isTogglingAutoUpdate ? 'wait' : 'pointer',
              transition: 'background 0.2s ease, opacity 0.2s ease',
              opacity: isTogglingAutoUpdate ? 0.6 : 1,
              outline: 'none',
              boxShadow: updateInfo?.auto_update?.enabled ? '0 0 8px rgba(16, 185, 129, 0.35)' : 'none',
            }}
            title={
              updateInfo?.auto_update?.enabled
                ? 'Auto Update is active (Idle safe). Click to disable.'
                : 'Auto Update is disabled. Click to enable.'
            }
          >
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: '#ffffff',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.4)',
                transform: updateInfo?.auto_update?.enabled ? 'translateX(14px)' : 'translateX(0px)',
                transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                display: 'block',
              }}
            />
          </button>
        </div>
      </div>

      {/* Update Available Alert Banner */}
      {updateInfo && (updateInfo.update_available || !updateInfo.is_synced) && (
        <div
          style={{
            margin: '12px 12px 0 12px',
            padding: '12px',
            borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.14), rgba(217, 119, 6, 0.08))',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            boxShadow: '0 4px 14px rgba(245, 158, 11, 0.1)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={14} color="#f59e0b" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24' }}>
                Update Available!
              </span>
            </div>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                background: '#f59e0b',
                color: '#000',
                padding: '1px 5px',
                borderRadius: 4,
                fontFamily: 'monospace',
              }}
            >
              v{updateInfo.latest_version}
            </span>
          </div>

          <div style={{ fontSize: 11, color: '#d6d3d1', lineHeight: 1.4 }}>
            {updateInfo.commits_behind > 0
              ? `Behind by ${updateInfo.commits_behind} commit${updateInfo.commits_behind > 1 ? 's' : ''} from remote origin.`
              : `Local version (v${updateInfo.current_version}) is out of sync with GitHub (v${updateInfo.latest_version}).`}
          </div>

          {updateInfo?.auto_update?.enabled && (
            <div
              style={{
                fontSize: 10,
                color: '#fde68a',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                background: 'rgba(245, 158, 11, 0.12)',
                padding: '4px 7px',
                borderRadius: 5,
              }}
            >
              <RefreshCw size={10} style={{ animation: 'spin 4s linear infinite', flexShrink: 0 }} />
              <span>Auto Update will install automatically once system is idle.</span>
            </div>
          )}

          <button
            onClick={handleGitPull}
            disabled={isPulling}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '7px 10px',
              borderRadius: 7,
              background: isPulling ? 'rgba(245, 158, 11, 0.3)' : 'linear-gradient(135deg, #f59e0b, #d97706)',
              border: 'none',
              color: isPulling ? '#fcd34d' : '#000000',
              fontWeight: 700,
              fontSize: 11,
              cursor: isPulling ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 8px rgba(245, 158, 11, 0.25)',
            }}
          >
            {isPulling ? (
              <>
                <RefreshCw size={12} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Pulling Updates...</span>
              </>
            ) : (
              <>
                <Download size={12} />
                <span>Update Now (git pull)</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Navigation Links */}
      <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: 4, overflowY: 'auto' }}>
        {navItems.map(item => {
          const isActive = currentRoute === item.id;
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '11px 14px',
                borderRadius: 10,
                background: isActive ? 'rgba(245, 158, 11, 0.14)' : 'transparent',
                border: `1px solid ${isActive ? 'rgba(245, 158, 11, 0.3)' : 'transparent'}`,
                color: isActive ? '#fbbf24' : '#a8a29e',
                fontSize: 13,
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textAlign: 'left',
                width: '100%',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                  e.currentTarget.style.color = '#fafaf9';
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#a8a29e';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: isActive ? '#f59e0b' : '#78716c' }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </div>
              {isActive && <ChevronRight size={14} color="#f59e0b" />}
            </button>
          );
        })}
      </nav>

      {/* Footer / System Status & Account Pill */}
      <div
        style={{
          padding: '16px',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          background: '#0a0806',
        }}
      >
        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
          <span style={{ color: '#78716c' }}>Gateway Stream</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                backgroundColor: isWsConnected ? '#10b981' : '#f59e0b',
                boxShadow: isWsConnected ? '0 0 8px #10b981' : 'none',
              }}
            />
            <span style={{ color: isWsConnected ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
              {isWsConnected ? 'Live' : 'Reconnecting'}
            </span>
          </div>
        </div>

        {/* Active Account Pill */}
        <div
          onClick={openSwitchAccountModal}
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(168, 162, 158, 0.15)',
            borderRadius: 10,
            padding: '10px 12px',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
          title="Click to switch active account"
        >
          <div style={{ minWidth: 0, flex: 1, marginRight: 8 }}>
            <div style={{ fontSize: 10, color: '#78716c', fontWeight: 600, textTransform: 'uppercase' }}>
              Active Identity
            </div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: '#fafaf9',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                marginTop: 2,
              }}
            >
              {activeAccount?.email || 'No Account Active'}
            </div>
          </div>
          <ArrowRightLeft size={14} color="#a8a29e" />
        </div>
      </div>
    </aside>
  );
};
