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
  Sparkles,
} from 'lucide-react';
import { Account, RoutePath } from '../types';

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
          padding: '24px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #f59e0b, #b45309)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            boxShadow: '0 4px 12px rgba(245, 158, 11, 0.3)',
          }}
        >
          <Sparkles size={20} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 15, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
              Prime Gate
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#f59e0b',
                background: 'rgba(245, 158, 11, 0.15)',
                padding: '2px 6px',
                borderRadius: 4,
              }}
            >
              v1.2.0
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', fontWeight: 500, marginTop: 2 }}>
            Antigravity Gateway
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: 4 }}>
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
