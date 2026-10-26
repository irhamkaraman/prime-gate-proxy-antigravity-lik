import React, { useState } from 'react';
import { useNavigation } from '../context/NavigationContext';
import { useToast } from '../context/ToastContext';
import { RefreshCw, Plus, Copy, Check, Menu, X } from 'lucide-react';
import { RoutePath } from '../types';

interface HeaderProps {
  onSyncQuota: () => Promise<void>;
  onOpenAddAccountModal: () => void;
  isSyncing: boolean;
  onLogout?: () => void;
  isMobileSidebarOpen?: boolean;
  onToggleMobileSidebar?: () => void;
}

const ROUTE_META: Record<RoutePath, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Token Telemetry & Traffic Radar',
    subtitle: 'Real-time throughput, granular token consumption, and live Google Antigravity quotas',
  },
  benchmarks: {
    title: 'Model Benchmarks & Request Hit Ledger',
    subtitle: 'Persistent database tracking, latency rankings, token splits, and quota depletion analysis',
  },
  caching: {
    title: 'Smart Semantic Caching Usage',
    subtitle: 'Zero-quota prompt caching layer, token economy ledger, and agent safety boundaries',
  },
  accounts: {
    title: 'Google Antigravity Accounts',
    subtitle: 'Manage connected OAuth accounts, switch active identity, or sync live model limits',
  },
  sandbox: {
    title: 'Prompt Sandbox & Model Playground',
    subtitle: 'Interactive test bench for streaming inference across Google Antigravity & OpenAI endpoints',
  },
  keys: {
    title: 'API Keys & Agent Integrations',
    subtitle: 'Generate and manage client API keys for Claude Code, OpenCode, Cline, Cursor, and Prompt Sandbox',
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
  isMobileSidebarOpen = false,
  onToggleMobileSidebar,
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
    <header className="app-header">
      <div className="app-header-left">
        {onToggleMobileSidebar && (
          <button
            type="button"
            onClick={onToggleMobileSidebar}
            className="btn-mobile-toggle"
            aria-label="Toggle navigation menu"
            title="Menu Navigasi"
          >
            {isMobileSidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        )}
        <div className="app-header-text">
          <h1 className="app-header-title">
            {meta.title}
          </h1>
          <p className="app-header-subtitle">
            {meta.subtitle}
          </p>
        </div>
      </div>

      <div className="app-header-actions">
        {/* Gateway URL copy pill */}
        <div
          onClick={handleCopyGatewayUrl}
          className="gateway-url-pill"
          title={`Click to copy gateway base URL (${gatewayUrl})`}
        >
          <span className="gateway-url-text">{gatewayUrl}</span>
          {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} color="#78716c" />}
        </div>

        {/* Sync button */}
        <button
          onClick={onSyncQuota}
          disabled={isSyncing}
          className="btn btn-secondary header-btn"
          title="Sync live quota and models from Google Antigravity"
        >
          <RefreshCw
            size={14}
            className={isSyncing ? 'animate-spin' : ''}
            style={{ animation: isSyncing ? 'spin 1s linear infinite' : 'none' }}
          />
          <span className="btn-text-full">{isSyncing ? 'Syncing...' : 'Sync Live'}</span>
          <span className="btn-text-short">{isSyncing ? 'Sync...' : 'Sync'}</span>
        </button>

        {/* Add Account button */}
        <button
          onClick={onOpenAddAccountModal}
          className="btn btn-primary header-btn"
          title="Add or connect Google Antigravity account"
        >
          <Plus size={15} />
          <span className="btn-text-full">Add Account</span>
          <span className="btn-text-short">Account</span>
        </button>
      </div>
    </header>
  );
};
