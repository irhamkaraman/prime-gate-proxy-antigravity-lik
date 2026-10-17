import React, { useState } from 'react';
import { useNavigation } from '../context/NavigationContext';
import { useToast } from '../context/ToastContext';
import { RefreshCw, Plus, Copy, Check, ExternalLink } from 'lucide-react';
import { RoutePath } from '../types';

interface HeaderProps {
  onSyncQuota: () => Promise<void>;
  onOpenAddAccountModal: () => void;
  isSyncing: boolean;
}

const ROUTE_META: Record<RoutePath, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Token Telemetry & Traffic Radar',
    subtitle: 'Real-time throughput, granular token consumption, and live Google Antigravity quotas',
  },
  accounts: {
    title: 'Google Antigravity Accounts',
    subtitle: 'Manage connected OAuth accounts, switch active identity, or sync live model limits',
  },
  sandbox: {
    title: 'Prompt Sandbox & Model Playground',
    subtitle: 'Interactive test bench for streaming inference across Google Antigravity & OpenAI endpoints',
  },
  sentinel: {
    title: 'System & Database Sentinel',
    subtitle: 'High-speed binary storage health, WAL-mode journals, and self-healing audit daemon',
  },
  docs: {
    title: 'Gateway Documentation & SDK Guide',
    subtitle: 'Integration instructions, curl examples, client configuration, and live API schemas',
  },
};

export const Header: React.FC<HeaderProps> = ({
  onSyncQuota,
  onOpenAddAccountModal,
  isSyncing,
}) => {
  const { currentRoute } = useNavigation();
  const { showToast } = useToast();
  const [copied, setCopied] = useState(false);

  const meta = ROUTE_META[currentRoute] || ROUTE_META.dashboard;
  const gatewayUrl = 'http://127.0.0.1:52111/v1';

  const handleCopyGatewayUrl = () => {
    navigator.clipboard.writeText(gatewayUrl).then(() => {
      setCopied(true);
      showToast('Gateway API endpoint copied to clipboard!', 'success');
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <header
      style={{
        padding: '20px 32px',
        borderBottom: '1px solid rgba(168, 162, 158, 0.12)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#0e0b08',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#fafaf9', letterSpacing: '-0.02em' }}>
          {meta.title}
        </h1>
        <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4 }}>
          {meta.subtitle}
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Gateway URL copy pill */}
        <div
          onClick={handleCopyGatewayUrl}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            borderRadius: 8,
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(168, 162, 158, 0.15)',
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            color: '#d6d3d1',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Click to copy gateway base URL"
        >
          <span>{gatewayUrl}</span>
          {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} color="#78716c" />}
        </div>

        {/* Sync button */}
        <button
          onClick={onSyncQuota}
          disabled={isSyncing}
          className="btn btn-secondary"
          title="Sync live quota and models from Google Antigravity"
        >
          <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} style={{ animation: isSyncing ? 'spin 1s linear infinite' : 'none' }} />
          <span>{isSyncing ? 'Syncing...' : 'Sync Live'}</span>
        </button>

        {/* Add Account button */}
        <button
          onClick={onOpenAddAccountModal}
          className="btn btn-primary"
        >
          <Plus size={15} />
          <span>Add Account</span>
        </button>
      </div>
    </header>
  );
};
