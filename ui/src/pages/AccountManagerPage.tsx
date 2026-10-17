import React, { useState, useEffect } from 'react';
import { Account, ModelInfo } from '../types';
import { useToast } from '../context/ToastContext';
import { useModal } from '../context/ModalContext';
import { useNavigation } from '../context/NavigationContext';
import {
  UserPlus,
  Trash2,
  ArrowRightLeft,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Copy,
  Check,
  Cpu,
  Sparkles,
  Brain,
  Eye,
  Layers,
  Zap,
  Play,
  Search,
  Filter,
} from 'lucide-react';

interface AccountManagerPageProps {
  accounts: Account[];
  activeAccount: Account | null;
  onRefresh: () => Promise<void>;
  onOpenAddModal: () => void;
}

export const AccountManagerPage: React.FC<AccountManagerPageProps> = ({
  accounts,
  activeAccount,
  onRefresh,
  onOpenAddModal,
}) => {
  const { showToast } = useToast();
  const { confirmAction } = useModal();
  const { navigate } = useNavigation();
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null);
  const [deletingEmail, setDeletingEmail] = useState<string | null>(null);

  // Models state
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState<boolean>(true);
  const [isRefreshingModels, setIsRefreshingModels] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'thinking' | 'multimodal' | 'google' | 'claude' | 'openai'>('all');
  const [copiedModelId, setCopiedModelId] = useState<string | null>(null);

  const fetchModels = async (forceRefresh: boolean = false) => {
    if (forceRefresh) setIsRefreshingModels(true);
    else setIsLoadingModels(true);

    try {
      const url = forceRefresh ? '/api/models/refresh' : '/v1/models';
      const method = forceRefresh ? 'POST' : 'GET';
      const res = await fetch(url, { method });
      if (res.ok) {
        const data = await res.json();
        const list: ModelInfo[] = Array.isArray(data)
          ? data
          : data.models || data.data || [];
        setModels(list);
        if (forceRefresh) {
          showToast(`Successfully refreshed ${list.length} models from Google Antigravity!`, 'success');
          await onRefresh();
        }
      }
    } catch (err) {
      console.error('Failed to load models:', err);
      if (forceRefresh) {
        showToast('Failed to refresh models from upstream', 'error');
      }
    } finally {
      setIsLoadingModels(false);
      setIsRefreshingModels(false);
    }
  };

  useEffect(() => {
    fetchModels(false);
  }, [activeAccount?.email]);

  const handleSwitchAccount = async (email: string) => {
    try {
      setSwitchingEmail(email);
      const res = await fetch(`/api/accounts/switch?email=${encodeURIComponent(email)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error('Failed to switch active account');
      showToast(`Active account switched to ${email}`, 'success');
      await onRefresh();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Failed to switch account', 'error');
    } finally {
      setSwitchingEmail(null);
    }
  };

  const handleDeleteAccount = (email: string) => {
    confirmAction({
      title: 'Delete Account',
      description: `Are you sure you want to remove ${email} from Prime Gate? Its OAuth credentials and cached quota will be permanently deleted.`,
      confirmText: 'Delete Account',
      confirmVariant: 'danger',
      onConfirm: async () => {
        try {
          setDeletingEmail(email);
          const res = await fetch(`/api/accounts/delete?email=${encodeURIComponent(email)}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
          });
          if (!res.ok) throw new Error('Failed to delete account');
          showToast(`Account ${email} deleted successfully`, 'success');
          await onRefresh();
        } catch (err: unknown) {
          showToast((err as Error).message || 'Failed to delete account', 'error');
        } finally {
          setDeletingEmail(null);
        }
      },
    });
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Banner / Active Account Card */}
      <div
        className="glass-card"
        style={{
          padding: '24px 28px',
          background: 'linear-gradient(135deg, #181310, #130f0c)',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 14,
              background: 'rgba(245, 158, 11, 0.15)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#f59e0b',
              fontSize: 22,
              fontWeight: 700,
            }}
          >
            {activeAccount?.email?.charAt(0).toUpperCase() || 'P'}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#ffffff' }}>
                {activeAccount?.email || 'No Active Account'}
              </span>
              <span className="badge badge-amber">Active Primary</span>
            </div>
            <div style={{ fontSize: 13, color: '#a8a29e', marginTop: 4 }}>
              Tier: <strong style={{ color: '#fbbf24' }}>{activeAccount?.tier || 'Antigravity Pro'}</strong> &bull; {activeAccount?.models_count || 14} Google Models Enabled &bull; Binary DB Synced
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={onOpenAddModal}
            className="btn btn-primary"
          >
            <UserPlus size={15} />
            <span>Connect Account</span>
          </button>
        </div>
      </div>

      {/* Accounts List Table */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
              Configured Accounts ({accounts.length})
            </h2>
            <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 3 }}>
              Google Antigravity accounts authenticated for multi-account rotation and quota balancing
            </p>
          </div>
          <button
            onClick={onRefresh}
            className="btn btn-secondary btn-sm"
          >
            <RefreshCw size={13} />
            <span>Refresh Table</span>
          </button>
        </div>

        {accounts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 24px', color: '#78716c' }}>
            <p style={{ fontSize: 15, fontWeight: 600, color: '#d6d3d1' }}>No Google Antigravity accounts connected</p>
            <p style={{ fontSize: 13, marginTop: 4 }}>Click "Connect Account" above to authenticate via Google OAuth.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {accounts.map(acc => {
              const isActive = acc.email === activeAccount?.email;
              return (
                <div
                  key={acc.email}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '16px 20px',
                    borderRadius: 12,
                    background: isActive ? 'rgba(245, 158, 11, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                    border: `1px solid ${isActive ? 'rgba(245, 158, 11, 0.3)' : 'rgba(255, 255, 255, 0.06)'}`,
                    transition: 'all 0.15s ease',
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 10,
                        background: isActive ? '#f59e0b' : 'rgba(255, 255, 255, 0.08)',
                        color: isActive ? '#090807' : '#d6d3d1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: 16,
                      }}
                    >
                      {acc.email.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14, fontWeight: 600, color: '#fafaf9' }}>
                          {acc.email}
                        </span>
                        {isActive && <span className="badge badge-amber">Active</span>}
                      </div>
                      <div style={{ fontSize: 12, color: '#78716c', marginTop: 2 }}>
                        {acc.tier || 'Antigravity Pro'} &bull; Added {acc.added_at ? new Date(acc.added_at).toLocaleDateString() : 'Recently'}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {!isActive && (
                      <button
                        onClick={() => handleSwitchAccount(acc.email)}
                        disabled={switchingEmail === acc.email}
                        className="btn btn-secondary btn-sm"
                      >
                        <ArrowRightLeft size={13} />
                        <span>{switchingEmail === acc.email ? 'Switching...' : 'Switch to Active'}</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleDeleteAccount(acc.email)}
                      disabled={deletingEmail === acc.email}
                      className="btn btn-danger btn-sm"
                      title="Delete account"
                    >
                      <Trash2 size={13} />
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Available Models & Specifications Card */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Cpu size={20} color="#f59e0b" />
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
                Available Antigravity Models ({models.length})
              </h2>
              <span className="badge badge-emerald">OpenAI /v1 Compatible</span>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4 }}>
              Live model catalog from binary database with reasoning limits, thinking budgets, and input modalities.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={() => fetchModels(true)}
              disabled={isRefreshingModels}
              className="btn btn-secondary btn-sm"
              title="Synchronize live models from Google Antigravity"
            >
              <RefreshCw size={13} style={{ animation: isRefreshingModels ? 'spin 1s linear infinite' : 'none' }} />
              <span>{isRefreshingModels ? 'Refreshing Models...' : 'Refresh Models'}</span>
            </button>
          </div>
        </div>

        {/* Search & Category Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 18 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 8,
              padding: '8px 12px',
              minWidth: 260,
              flex: 1,
              maxWidth: 400,
            }}
          >
            <Search size={14} color="#78716c" />
            <input
              type="text"
              placeholder="Filter models by ID, name, or provider..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#f5f5f4',
                fontSize: 13,
                outline: 'none',
                width: '100%',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {(
              [
                { id: 'all', label: 'All Models' },
                { id: 'thinking', label: 'Reasoning / Thinking' },
                { id: 'multimodal', label: 'Multimodal' },
                { id: 'google', label: 'Google' },
                { id: 'claude', label: 'Claude' },
                { id: 'openai', label: 'OpenAI' },
              ] as const
            ).map((f) => (
              <button
                key={f.id}
                onClick={() => setActiveFilter(f.id)}
                className={`btn btn-sm ${activeFilter === f.id ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 12px', fontSize: 12 }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Models List */}
        {isLoadingModels ? (
          <div style={{ textAlign: 'center', padding: '36px 20px', color: '#78716c' }}>
            <RefreshCw size={20} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 8px auto' }} />
            <p style={{ fontSize: 13 }}>Loading live model catalog from database...</p>
          </div>
        ) : (
          (() => {
            const formatTokens = (count?: number) => {
              if (!count) return '1M';
              if (count >= 1000000) return `${(count / 1000000).toFixed(count % 1000000 === 0 ? 0 : 1)}M`;
              if (count >= 1000) return `${Math.round(count / 1000)}K`;
              return `${count}`;
            };

            const filteredModels = models.filter((m) => {
              const q = searchQuery.toLowerCase();
              const matchesSearch =
                !q ||
                m.id.toLowerCase().includes(q) ||
                (m.name && m.name.toLowerCase().includes(q)) ||
                (m.upstream_provider && m.upstream_provider.toLowerCase().includes(q));

              if (!matchesSearch) return false;

              if (activeFilter === 'thinking') {
                return m.supports_thinking || m.capabilities?.thinking;
              }
              if (activeFilter === 'multimodal') {
                return m.multimodal || m.capabilities?.multimodal || m.supports_images;
              }
              if (activeFilter === 'google') {
                return (m.upstream_provider || '').toLowerCase().includes('google') || m.id.toLowerCase().includes('gemini');
              }
              if (activeFilter === 'claude') {
                return (m.upstream_provider || '').toLowerCase().includes('anthropic') || m.id.toLowerCase().includes('claude');
              }
              if (activeFilter === 'openai') {
                return (m.upstream_provider || '').toLowerCase().includes('openai') || m.id.toLowerCase().includes('gpt');
              }
              return true;
            });

            if (filteredModels.length === 0) {
              return (
                <div style={{ textAlign: 'center', padding: '36px 20px', color: '#78716c' }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#d6d3d1' }}>No matching models found</p>
                  <p style={{ fontSize: 12, marginTop: 4 }}>Try adjusting your search query or filter selection.</p>
                </div>
              );
            }

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {filteredModels.map((m) => {
                  const isCopied = copiedModelId === m.id;
                  const isThinking = m.supports_thinking || m.capabilities?.thinking;
                  const isMulti = m.multimodal || m.capabilities?.multimodal || m.supports_images;
                  const providerName = m.upstream_provider || (m.id.includes('claude') ? 'Anthropic' : m.id.includes('gpt') ? 'OpenAI' : 'Google');

                  return (
                    <div
                      key={m.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '16px 20px',
                        borderRadius: 12,
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        flexWrap: 'wrap',
                        gap: 14,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {/* Left: Model Name & ID */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 260 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 14, fontWeight: 700, color: '#ffffff' }}>
                            {m.name || m.id}
                          </span>
                          {m.recommended && <span className="badge badge-amber">Recommended</span>}
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 999,
                              background: providerName === 'Anthropic' ? 'rgba(168, 85, 247, 0.15)' : providerName === 'OpenAI' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                              color: providerName === 'Anthropic' ? '#c084fc' : providerName === 'OpenAI' ? '#34d399' : '#fbbf24',
                              border: `1px solid ${providerName === 'Anthropic' ? 'rgba(168, 85, 247, 0.3)' : providerName === 'OpenAI' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                              textTransform: 'uppercase',
                            }}
                          >
                            {providerName}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <code style={{ fontSize: 12, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                            {m.id}
                          </code>
                        </div>
                      </div>

                      {/* Middle: Capabilities Tags */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', flex: 1, justifyContent: 'flex-start' }}>
                        {/* Thinking Tag */}
                        {isThinking ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 5,
                              fontSize: 11,
                              fontWeight: 600,
                              padding: '3px 9px',
                              borderRadius: 6,
                              background: 'rgba(245, 158, 11, 0.12)',
                              color: '#fbbf24',
                              border: '1px solid rgba(245, 158, 11, 0.25)',
                            }}
                          >
                            <Brain size={12} />
                            <span>{m.thinking_desc || 'Thinking Supported'}</span>
                          </span>
                        ) : (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 5,
                              fontSize: 11,
                              fontWeight: 500,
                              padding: '3px 8px',
                              borderRadius: 6,
                              background: 'rgba(255, 255, 255, 0.04)',
                              color: '#78716c',
                            }}
                          >
                            Standard Mode
                          </span>
                        )}

                        {/* Modalities Tag */}
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            fontSize: 11,
                            fontWeight: 600,
                            padding: '3px 9px',
                            borderRadius: 6,
                            background: isMulti ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                            color: isMulti ? '#38bdf8' : '#a8a29e',
                            border: isMulti ? '1px solid rgba(56, 189, 248, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
                          }}
                        >
                          {isMulti ? <Eye size={12} /> : null}
                          <span>{isMulti ? (m.supports_video ? 'Multimodal (Vision + Audio)' : 'Vision / Images') : 'Text Only'}</span>
                        </span>

                        {/* Context Window Tag */}
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            fontSize: 11,
                            fontWeight: 600,
                            padding: '3px 9px',
                            borderRadius: 6,
                            background: 'rgba(168, 85, 247, 0.1)',
                            color: '#c084fc',
                            border: '1px solid rgba(168, 85, 247, 0.2)',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          <Layers size={11} />
                          <span>{formatTokens(m.context_window)} Context</span>
                        </span>

                        {/* Streaming Tag */}
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 11,
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: 6,
                            background: 'rgba(16, 185, 129, 0.1)',
                            color: '#34d399',
                            border: '1px solid rgba(16, 185, 129, 0.2)',
                          }}
                        >
                          <Zap size={11} />
                          <span>Streaming</span>
                        </span>
                      </div>

                      {/* Right Actions */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(m.id).then(() => {
                              setCopiedModelId(m.id);
                              showToast(`Model ID '${m.id}' copied to clipboard!`, 'success');
                              setTimeout(() => setCopiedModelId(null), 2000);
                            });
                          }}
                          className="btn btn-secondary btn-sm"
                          title="Copy model identifier for OpenAI API requests"
                          style={{ padding: '6px 10px', fontSize: 12 }}
                        >
                          {isCopied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                          <span>{isCopied ? 'Copied' : 'Copy ID'}</span>
                        </button>

                        <button
                          onClick={() => {
                            sessionStorage.setItem('selected_sandbox_model', m.id);
                            navigate('sandbox');
                            showToast(`Loaded ${m.id} in Prompt Sandbox`, 'info');
                          }}
                          className="btn btn-primary btn-sm"
                          title="Test this model in the Prompt Sandbox"
                          style={{ padding: '6px 12px', fontSize: 12 }}
                        >
                          <Play size={12} />
                          <span>Sandbox</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
};
