import React, { useState, useEffect } from 'react';
import { useToast } from '../context/ToastContext';
import { useModal } from '../context/ModalContext';
import {
  KeyRound,
  Plus,
  Copy,
  Check,
  Trash2,
  Shield,
  Terminal,
  Code,
  AlertTriangle,
  Sparkles,
  ExternalLink,
  X,
  Lock,
  Cpu
} from 'lucide-react';

interface ApiKeyItem {
  id: string | number;
  name: string;
  prefix: string;
  created_at: string | number;
  last_used_at?: string | number;
  is_active: boolean;
  rate_limit_rpm?: number;
  rate_limit_tpd?: number;
  quota_credits?: number;
  allowed_models?: string | string[];
  cache_scope?: 'shared' | 'key' | 'disabled';
}

export const ApiKeysPage: React.FC = () => {
  const { showToast } = useToast();
  const { confirmAction } = useModal();

  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeKey, setActiveKey] = useState<string>(() => localStorage.getItem('pg_active_api_key') || '');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [newRpm, setNewRpm] = useState<number>(0);
  const [newTpd, setNewTpd] = useState<number>(0);
  const [newCacheScope, setNewCacheScope] = useState<'shared' | 'key' | 'disabled'>('shared');
  const [newAllowedModels, setNewAllowedModels] = useState<string[]>([]);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createdRawKey, setCreatedRawKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [selectedAgentTab, setSelectedAgentTab] = useState<'claude' | 'opencode' | 'cline' | 'cursor' | 'aider' | 'curl'>('claude');
  const [copiedSnippet, setCopiedSnippet] = useState<boolean>(false);

  const fetchKeys = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/auth/keys');
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || []);
      } else if (res.status === 401) {
        showToast('Dashboard session unauthorized. Please log in.', 'error');
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
      showToast('Failed to load registered API keys', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const res = await fetch('/api/models');
      if (res.ok) {
        const data = await res.json();
        const rawList = data.models || data.data || [];
        const ids = rawList.map((m: any) => m.id || m.name || m).filter(Boolean);
        setAvailableModels(ids);
      }
    } catch (err) {
      console.warn('Failed to fetch model catalog:', err);
    }
  };

  useEffect(() => {
    fetchKeys();
    fetchAvailableModels();
  }, []);

  const handleCreateKey = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!newKeyName.trim()) {
      showToast('Please enter a descriptive name for this API key', 'warning');
      return;
    }
    setIsCreating(true);
    try {
      const res = await fetch('/api/auth/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newKeyName.trim(),
          rate_limit_rpm: Number(newRpm) || 0,
          rate_limit_tpd: Number(newTpd) || 0,
          allowed_models: JSON.stringify(newAllowedModels),
          cache_scope: newCacheScope
        })
      });
      if (res.ok) {
        const data = await res.json();
        const raw = data.raw_key;
        setCreatedRawKey(raw);
        localStorage.setItem('pg_active_api_key', raw);
        setActiveKey(raw);
        showToast('API Key generated successfully & synced with Prompt Sandbox!', 'success');
        fetchKeys();
      } else {
        showToast('Failed to create API key', 'error');
      }
    } catch {
      showToast('Network error while creating API key', 'error');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevokeKey = (keyItem: ApiKeyItem) => {
    confirmAction({
      title: 'Revoke API Key',
      description: `Are you sure you want to permanently revoke API key "${keyItem.name}" (${keyItem.prefix}...)? Any agent or tool currently using this key will immediately be blocked with HTTP 401 Unauthorized.`,
      confirmText: 'Revoke Key',
      confirmVariant: 'danger',
      onConfirm: async () => {
        try {
          const res = await fetch(`/api/auth/keys/${keyItem.id}`, {
            method: 'DELETE'
          });
          if (res.ok) {
            showToast(`API Key "${keyItem.name}" revoked successfully`, 'success');
            // If the revoked key was stored in active sandbox, remove it
            if (activeKey.startsWith(keyItem.prefix)) {
              localStorage.removeItem('pg_active_api_key');
              setActiveKey('');
            }
            fetchKeys();
          } else {
            showToast('Failed to revoke API key', 'error');
          }
        } catch {
          showToast('Error revoking API key', 'error');
        }
      }
    });
  };

  const handleCopyRawKey = () => {
    if (!createdRawKey) return;
    navigator.clipboard.writeText(createdRawKey).then(() => {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
      showToast('API key copied to clipboard! Keep it secure.', 'success');
    });
  };

  const handleManualSaveKey = (val: string) => {
    const trimmed = val.trim();
    if (trimmed) {
      localStorage.setItem('pg_active_api_key', trimmed);
      setActiveKey(trimmed);
      showToast('Active API key saved for Prompt Sandbox!', 'success');
    } else {
      localStorage.removeItem('pg_active_api_key');
      setActiveKey('');
      showToast('Active Sandbox API key cleared', 'info');
    }
  };

  const currentDisplayKey = activeKey.trim() || createdRawKey || 'YOUR_PRIMEGATE_API_KEY';

  const agentSnippets: Record<string, string> = {
    claude: `# Claude Code CLI Setup (Anthropic Native Protocol)
export ANTHROPIC_BASE_URL="http://127.0.0.1:52111"
export ANTHROPIC_API_KEY="${currentDisplayKey}"

# Launch Claude Code:
claude --model claude-3-7-sonnet`,

    opencode: `# OpenCode Setup (OpenAI Protocol)
# Add to ~/.config/opencode/config.json:
{
  "api_endpoint": "http://127.0.0.1:52111/v1",
  "api_key": "${currentDisplayKey}",
  "model": "claude-3-7-sonnet"
}`,

    cline: `# Cline / Roo Code (VS Code Extension)
# In Settings -> API Provider: Select "Anthropic Compatible"
Base URL: http://127.0.0.1:52111
API Key:  ${currentDisplayKey}
Model ID: claude-3-7-sonnet (or gemini-2.5-flash)`,

    cursor: `# Cursor IDE Configuration
# In Cursor Settings -> Models -> OpenAI API Key:
Override OpenAI Base URL: http://127.0.0.1:52111/v1
OpenAI API Key:          ${currentDisplayKey}
Models: claude-3-7-sonnet, gemini-2.5-flash, gemini-3.8-flash`,

    aider: `# Aider CLI Setup (Terminal Pair Programmer)
export OPENAI_API_BASE="http://127.0.0.1:52111/v1"
export OPENAI_API_KEY="${currentDisplayKey}"

aider --model openai/claude-3-7-sonnet`,

    curl: `# cURL Test (OpenAI Compatible Endpoint)
curl -X POST http://127.0.0.1:52111/v1/chat/completions \\
  -H "Authorization: Bearer ${currentDisplayKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Hello Prime Gate!"}]
  }'`
  };

  const handleCopySnippet = () => {
    const text = agentSnippets[selectedAgentTab];
    navigator.clipboard.writeText(text).then(() => {
      setCopiedSnippet(true);
      setTimeout(() => setCopiedSnippet(false), 2000);
      showToast('Agent configuration snippet copied!', 'success');
    });
  };

  const formatDate = (val: string | number | undefined) => {
    if (!val) return '-';
    const num = typeof val === 'number' ? val : parseFloat(val);
    if (!isNaN(num)) {
      const ms = num < 10000000000 ? num * 1000 : num;
      return new Date(ms).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
    return new Date(val).toLocaleDateString();
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* 1. Header Banner */}
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
          gap: 16
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
              color: '#f59e0b'
            }}
          >
            <KeyRound size={26} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 20, fontWeight: 700, color: '#ffffff', margin: 0 }}>
                API Keys & Agent Integrations
              </h1>
              <span className="badge badge-amber">v1.2.4 Security</span>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4, margin: '4px 0 0 0' }}>
              Generate, manage, and configure client API keys for Claude Code, OpenCode, Cline, Cursor, Aider, and Prompt Sandbox.
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            setCreatedRawKey(null);
            setNewKeyName('');
            setNewRpm(0);
            setNewTpd(0);
            setNewCacheScope('shared');
            setNewAllowedModels([]);
            setIsCreateModalOpen(true);
          }}
          className="btn btn-primary"
        >
          <Plus size={16} />
          <span>Create New API Key</span>
        </button>
      </div>

      {/* 2. Active Key for Sandbox Card */}
      <div
        className="glass-card"
        style={{
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16
        }}
      >
        <div style={{ flex: '1 1 320px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#fafaf9' }}>
              Active Browser & Sandbox Key
            </span>
            {activeKey ? (
              <span className="badge badge-emerald">
                <Check size={12} /> Ready for Sandbox
              </span>
            ) : (
              <span className="badge badge-amber">
                <AlertTriangle size={12} /> No Key Active (Sandbox Will Fail 401)
              </span>
            )}
          </div>
          <p style={{ fontSize: 12, color: '#a8a29e', margin: 0 }}>
            This key is stored locally in your browser and automatically sent in all Prompt Sandbox requests via{' '}
            <code style={{ color: '#fbbf24', background: 'rgba(255, 255, 255, 0.05)', padding: '2px 5px', borderRadius: 4 }}>
              Authorization: Bearer
            </code>{' '}
            and{' '}
            <code style={{ color: '#fbbf24', background: 'rgba(255, 255, 255, 0.05)', padding: '2px 5px', borderRadius: 4 }}>
              x-api-key
            </code>.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', width: '100%', maxWidth: 440 }}>
          <input
            type="password"
            value={activeKey}
            onChange={(e) => setActiveKey(e.target.value)}
            placeholder="Paste raw pg-live-... key here"
            style={{
              flex: 1,
              minWidth: 220,
              padding: '9px 14px',
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 8,
              color: '#ffffff',
              outline: 'none'
            }}
          />
          <button
            onClick={() => handleManualSaveKey(activeKey)}
            className="btn btn-secondary"
            style={{ padding: '9px 16px', fontSize: 12 }}
          >
            Save Key
          </button>
        </div>
      </div>

      {/* 3. One-Click Coding Agent Setup Card */}
      <div className="glass-card" style={{ padding: '24px 28px', overflow: 'hidden' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            marginBottom: 18
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Terminal size={20} color="#f59e0b" />
            <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', margin: 0 }}>
              One-Click Coding Agent Setup
            </h2>
          </div>

          <button
            onClick={handleCopySnippet}
            className="btn btn-secondary btn-sm"
          >
            {copiedSnippet ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
            <span>{copiedSnippet ? 'Copied Configuration!' : 'Copy Code Snippet'}</span>
          </button>
        </div>

        {/* Agent Tabs */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            padding: '4px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: 10,
            border: '1px solid rgba(255, 255, 255, 0.06)',
            marginBottom: 16
          }}
        >
          {[
            { id: 'claude', label: 'Claude Code CLI' },
            { id: 'opencode', label: 'OpenCode' },
            { id: 'cline', label: 'Cline / Roo Code' },
            { id: 'cursor', label: 'Cursor IDE' },
            { id: 'aider', label: 'Aider' },
            { id: 'curl', label: 'cURL' }
          ].map(tab => {
            const isSelected = selectedAgentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setSelectedAgentTab(tab.id as any)}
                style={{
                  padding: '7px 14px',
                  fontSize: 12,
                  fontWeight: isSelected ? 700 : 500,
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  background: isSelected ? 'rgba(245, 158, 11, 0.2)' : 'transparent',
                  color: isSelected ? '#fbbf24' : '#a8a29e'
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Snippet Code View */}
        <div
          style={{
            background: '#0a0807',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 10,
            padding: '16px 20px',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            overflowX: 'auto',
            lineHeight: 1.6,
            color: '#e4e4e7'
          }}
        >
          <pre style={{ margin: 0, fontFamily: 'inherit' }}>{agentSnippets[selectedAgentTab]}</pre>
        </div>
      </div>

      {/* 4. Registered API Keys Table */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            marginBottom: 20
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Shield size={18} color="#f59e0b" />
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', margin: 0 }}>
                Registered API Keys
              </h2>
              <span className="badge badge-neutral">{keys.length} Active</span>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4, margin: '4px 0 0 0' }}>
              Cryptographically hashed keys accepted for `/v1/chat/completions` and `/v1/messages`.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div style={{ padding: '36px', textAlign: 'center', color: '#a8a29e', fontSize: 14 }}>
            Loading registered keys...
          </div>
        ) : keys.length === 0 ? (
          <div
            style={{
              padding: '36px',
              textAlign: 'center',
              background: 'rgba(255, 255, 255, 0.02)',
              borderRadius: 10,
              border: '1px dashed rgba(255, 255, 255, 0.1)'
            }}
          >
            <KeyRound size={32} color="#78716c" style={{ marginBottom: 10 }} />
            <p style={{ fontSize: 14, color: '#a8a29e', margin: '0 0 12px 0' }}>
              No API keys found. Create a key to authenticate Claude Code, OpenCode, and Prompt Sandbox.
            </p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="btn btn-primary"
            >
              <Plus size={15} />
              <span>Create First Key</span>
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>KEY NAME</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>PREFIX</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>POLICY LIMITS</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>CACHE SCOPE</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>MODELS</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>LAST USED</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c' }}>STATUS</th>
                  <th style={{ padding: '12px 16px', fontSize: 12, fontWeight: 600, color: '#78716c', textAlign: 'right' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr
                    key={String(k.id)}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                      transition: 'background 0.15s ease'
                    }}
                  >
                    <td style={{ padding: '14px 16px', fontSize: 13, fontWeight: 600, color: '#ffffff' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Lock size={14} color="#f59e0b" />
                        <span>{k.name}</span>
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: 12, fontFamily: 'var(--font-mono)', color: '#fbbf24' }}>
                      <span
                        style={{
                          background: 'rgba(245, 158, 11, 0.1)',
                          border: '1px solid rgba(245, 158, 11, 0.25)',
                          padding: '3px 8px',
                          borderRadius: 6
                        }}
                      >
                        {k.prefix}...
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 11, color: '#78716c' }}>RPM:</span>
                          {k.rate_limit_rpm ? (
                            <span className="badge badge-amber">{k.rate_limit_rpm} req/m</span>
                          ) : (
                            <span style={{ color: '#a8a29e', fontSize: 11 }}>Unlimited</span>
                          )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 11, color: '#78716c' }}>TPD:</span>
                          {k.rate_limit_tpd ? (
                            <span className="badge badge-cyan">{k.rate_limit_tpd.toLocaleString()} tokens</span>
                          ) : (
                            <span style={{ color: '#a8a29e', fontSize: 11 }}>Unlimited</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: 12 }}>
                      {k.cache_scope === 'key' ? (
                        <span className="badge badge-emerald">Isolated (Key)</span>
                      ) : k.cache_scope === 'disabled' ? (
                        <span className="badge badge-neutral">Bypass</span>
                      ) : (
                        <span className="badge badge-neutral">Shared</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: 12 }}>
                      {(() => {
                        try {
                          const m = typeof k.allowed_models === 'string' ? JSON.parse(k.allowed_models) : (k.allowed_models || []);
                          if (!m || m.length === 0 || m.includes('*')) {
                            return <span style={{ color: '#a8a29e', fontSize: 11 }}>All models (*)</span>;
                          }
                          return (
                            <span className="badge badge-amber" title={m.join(', ')}>
                              {m.length} allowed
                            </span>
                          );
                        } catch {
                          return <span style={{ color: '#a8a29e', fontSize: 11 }}>All models (*)</span>;
                        }
                      })()}
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: 12, color: '#a8a29e' }}>
                      {k.last_used_at ? formatDate(k.last_used_at) : 'Never'}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span className="badge badge-emerald">Active</span>
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleRevokeKey(k)}
                        className="btn btn-danger btn-sm"
                        title="Revoke API Key"
                      >
                        <Trash2 size={13} />
                        <span>Revoke</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Custom Modal for Creating API Key & Displaying Token */}
      {isCreateModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !createdRawKey) {
              setIsCreateModalOpen(false);
            }
          }}
        >
          <div
            className="animate-fade-in"
            style={{
              background: '#15110e',
              border: '1px solid rgba(168, 162, 158, 0.2)',
              borderRadius: 16,
              maxWidth: 520,
              width: '100%',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)',
              overflow: 'hidden'
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '20px 24px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <KeyRound size={20} color="#f59e0b" />
                <h3 style={{ fontSize: 17, fontWeight: 700, color: '#fafaf9', margin: 0 }}>
                  {createdRawKey ? 'API Key Created Successfully' : 'Generate New API Key'}
                </h3>
              </div>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#78716c',
                  cursor: 'pointer',
                  padding: 4,
                  display: 'flex'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px' }}>
              {!createdRawKey ? (
                <form onSubmit={handleCreateKey}>
                  <p style={{ fontSize: 13, color: '#a8a29e', margin: '0 0 16px 0', lineHeight: 1.5 }}>
                    Give your API key a recognizable name to track usage across different coding agents or environments.
                  </p>

                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#fafaf9', marginBottom: 8 }}>
                    KEY NAME / CLIENT IDENTIFIER
                  </label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g. claude-code-cli, opencode, cursor-ide"
                    autoFocus
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      fontSize: 13,
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: 8,
                      color: '#ffffff',
                      outline: 'none',
                      marginBottom: 16
                    }}
                  />

                  {/* Suggestions pills */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 18 }}>
                    <span style={{ fontSize: 11, color: '#78716c', alignSelf: 'center', marginRight: 4 }}>
                      Suggestions:
                    </span>
                    {['claude-code', 'opencode', 'cline-agent', 'cursor-ide', 'aider'].map(sugg => (
                      <button
                        type="button"
                        key={sugg}
                        onClick={() => setNewKeyName(sugg)}
                        style={{
                          padding: '3px 8px',
                          fontSize: 11,
                          borderRadius: 6,
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          color: '#a8a29e',
                          cursor: 'pointer'
                        }}
                      >
                        {sugg}
                      </button>
                    ))}
                  </div>

                  {/* Policy Limits (RPM & TPD) */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#fafaf9', marginBottom: 6 }}>
                        RATE LIMIT (RPM)
                      </label>
                      <input
                        type="number"
                        min="0"
                        value={newRpm}
                        onChange={(e) => setNewRpm(Math.max(0, parseInt(e.target.value) || 0))}
                        placeholder="0 = Unlimited"
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          fontSize: 12,
                          background: 'rgba(255, 255, 255, 0.04)',
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                          borderRadius: 8,
                          color: '#ffffff',
                          outline: 'none'
                        }}
                      />
                      <span style={{ fontSize: 10, color: '#78716c', display: 'block', marginTop: 3 }}>
                        0 = Unlimited req/min
                      </span>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#fafaf9', marginBottom: 6 }}>
                        DAILY TOKEN QUOTA (TPD)
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="1000"
                        value={newTpd}
                        onChange={(e) => setNewTpd(Math.max(0, parseInt(e.target.value) || 0))}
                        placeholder="0 = Unlimited"
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          fontSize: 12,
                          background: 'rgba(255, 255, 255, 0.04)',
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                          borderRadius: 8,
                          color: '#ffffff',
                          outline: 'none'
                        }}
                      />
                      <span style={{ fontSize: 10, color: '#78716c', display: 'block', marginTop: 3 }}>
                        0 = Unlimited tokens/day
                      </span>
                    </div>
                  </div>

                  {/* Cache Scope */}
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#fafaf9', marginBottom: 6 }}>
                      CACHE ISOLATION SCOPE
                    </label>
                    <select
                      value={newCacheScope}
                      onChange={(e) => setNewCacheScope(e.target.value as any)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        fontSize: 12,
                        background: '#15110e',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: 8,
                        color: '#ffffff',
                        outline: 'none'
                      }}
                    >
                      <option value="shared">Shared (Global cache across developers)</option>
                      <option value="key">Isolated (Dedicated semantic cache per API key)</option>
                      <option value="disabled">Disabled (Bypass cache completely)</option>
                    </select>
                  </div>

                  {/* Allowed Models Whitelist (Dynamic from DB) */}
                  {availableModels.length > 0 && (
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <label style={{ fontSize: 11, fontWeight: 600, color: '#fafaf9', margin: 0 }}>
                          ALLOWED MODELS WHITELIST
                        </label>
                        {newAllowedModels.length > 0 && (
                          <button
                            type="button"
                            onClick={() => setNewAllowedModels([])}
                            style={{ background: 'none', border: 'none', color: '#f59e0b', fontSize: 11, cursor: 'pointer' }}
                          >
                            Allow All (*)
                          </button>
                        )}
                      </div>
                      <p style={{ fontSize: 11, color: '#78716c', margin: '0 0 8px 0' }}>
                        Click to select specific models, or leave unselected to allow all active models.
                      </p>
                      <div style={{ maxHeight: 90, overflowY: 'auto', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {availableModels.map(mid => {
                          const isSelected = newAllowedModels.includes(mid);
                          return (
                            <button
                              type="button"
                              key={mid}
                              onClick={() => {
                                if (isSelected) {
                                  setNewAllowedModels(newAllowedModels.filter(m => m !== mid));
                                } else {
                                  setNewAllowedModels([...newAllowedModels, mid]);
                                }
                              }}
                              style={{
                                padding: '3px 8px',
                                fontSize: 11,
                                borderRadius: 6,
                                background: isSelected ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                                border: isSelected ? '1px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.08)',
                                color: isSelected ? '#fbbf24' : '#a8a29e',
                                cursor: 'pointer'
                              }}
                            >
                              {mid}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button
                      type="button"
                      onClick={() => setIsCreateModalOpen(false)}
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isCreating}
                      className="btn btn-primary"
                    >
                      <Sparkles size={15} />
                      <span>{isCreating ? 'Generating...' : 'Generate API Key'}</span>
                    </button>
                  </div>
                </form>
              ) : (
                <div>
                  <div
                    style={{
                      padding: '12px 16px',
                      background: 'rgba(245, 158, 11, 0.12)',
                      border: '1px solid rgba(245, 158, 11, 0.3)',
                      borderRadius: 10,
                      color: '#fbbf24',
                      fontSize: 12,
                      display: 'flex',
                      gap: 10,
                      marginBottom: 16,
                      lineHeight: 1.5
                    }}
                  >
                    <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>
                      <strong>Important:</strong> Copy your API key now. For your security, this key is cryptographically hashed and cannot be viewed again.
                    </span>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: '#090807',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      marginBottom: 16
                    }}
                  >
                    <input
                      type="text"
                      readOnly
                      value={createdRawKey}
                      style={{
                        flex: 1,
                        background: 'transparent',
                        border: 'none',
                        color: '#34d399',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                        outline: 'none'
                      }}
                    />
                    <button
                      onClick={handleCopyRawKey}
                      className="btn btn-primary btn-sm"
                      style={{ marginLeft: 8 }}
                    >
                      {copiedKey ? <Check size={14} /> : <Copy size={14} />}
                      <span>{copiedKey ? 'Copied!' : 'Copy'}</span>
                    </button>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => {
                        setIsCreateModalOpen(false);
                        setCreatedRawKey(null);
                      }}
                      className="btn btn-secondary"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
