import React, { useState, useEffect } from 'react';
import { TelemetryMetrics, Account, TokenVolumePoint, ModelBenchmarksResponse, TimeRange } from '../types';
import { TokenChart } from '../components/TokenChart';
import { useToast } from '../context/ToastContext';
import { useNavigation } from '../context/NavigationContext';
import {
  Zap,
  Clock,
  Layers,
  Copy,
  Check,
  RefreshCw,
  Cpu,
  ShieldCheck,
  Sparkles,
  BarChart3,
  ArrowRight,
  Flame,
} from 'lucide-react';

interface DashboardPageProps {
  metrics: TelemetryMetrics;
  activeAccount: Account | null;
  chartPoints: TokenVolumePoint[];
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  onSyncQuota: () => Promise<void>;
  isSyncing: boolean;
  lastLedgerUpdate?: number;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  metrics,
  activeAccount,
  chartPoints,
  timeRange,
  onTimeRangeChange,
  onSyncQuota,
  isSyncing,
  lastLedgerUpdate,
}) => {
  const { showToast } = useToast();
  const { navigate } = useNavigation();
  const [benchmarks, setBenchmarks] = useState<ModelBenchmarksResponse | null>(null);
  const [currency, setCurrency] = useState<'USD' | 'IDR'>('IDR');
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedAnthropicUrl, setCopiedAnthropicUrl] = useState(false);

  useEffect(() => {
    fetch('/api/analytics/models')
      .then(res => res.json())
      .then(data => setBenchmarks(data))
      .catch(err => console.debug('Failed to load benchmarks on dashboard:', err));
  }, [lastLedgerUpdate]);

  const gatewayUrl = 'http://127.0.0.1:52111/v1';
  const anthropicGatewayUrl = 'http://127.0.0.1:52111';
  const apiKey = 'prime-gate-proxy';

  const copyToClipboard = (text: string, type: 'url' | 'anthropic_url' | 'key') => {
    navigator.clipboard.writeText(text).then(() => {
      if (type === 'url') {
        setCopiedUrl(true);
        setTimeout(() => setCopiedUrl(false), 2000);
      } else if (type === 'anthropic_url') {
        setCopiedAnthropicUrl(true);
        setTimeout(() => setCopiedAnthropicUrl(false), 2000);
      } else {
        setCopiedKey(true);
        setTimeout(() => setCopiedKey(false), 2000);
      }
      showToast(`${type.includes('url') ? 'Endpoint URL' : 'API Key'} copied to clipboard!`, 'success');
    });
  };

  const quotaItems = activeAccount?.quota_summary && activeAccount.quota_summary.length > 0
    ? activeAccount.quota_summary
    : [];

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* 5 Stat Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
        }}
      >
        {/* Card 1: Throughput */}
        <div
          className="glass-card"
          style={{
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            minHeight: 142,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Throughput Speed</span>
            <div className="pulse-dot" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.throughput_tokens_per_sec.toFixed(1)}
            </span>
            <span style={{ fontSize: 12, color: '#78716c' }}>tokens / sec</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 8 }}>
            Active rolling output rate
          </div>
        </div>

        {/* Card 2: Tokens Consumed Today */}
        <div
          className="glass-card"
          style={{
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            minHeight: 142,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Tokens Consumed Today</span>
            <span className="badge badge-amber">24h Rolling</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.tokens_today.total.toLocaleString()}
            </span>
            <span style={{ fontSize: 12, color: '#78716c' }}>tokens</span>
          </div>
          <div
            style={{
              fontSize: 11,
              color: '#78716c',
              marginTop: 8,
              fontFamily: 'var(--font-mono)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={`Prompt: ${metrics.tokens_today.prompt.toLocaleString()} • Comp: ${metrics.tokens_today.completion.toLocaleString()} • Think: ${metrics.tokens_today.reasoning.toLocaleString()}`}
          >
            Prompt: {metrics.tokens_today.prompt.toLocaleString()} &bull; Comp: {metrics.tokens_today.completion.toLocaleString()}
          </div>
        </div>

        {/* Card 3: Economic Value Delivered */}
        <div
          className="glass-card"
          style={{
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            minHeight: 142,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Value Delivered</span>
            <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(255, 255, 255, 0.06)', borderRadius: 6, padding: '2px 4px', gap: 2 }}>
              <button
                onClick={() => setCurrency('IDR')}
                style={{
                  border: 'none',
                  background: currency === 'IDR' ? '#f59e0b' : 'transparent',
                  color: currency === 'IDR' ? '#000000' : '#a8a29e',
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 4,
                  padding: '2px 6px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                IDR
              </button>
              <button
                onClick={() => setCurrency('USD')}
                style={{
                  border: 'none',
                  background: currency === 'USD' ? '#f59e0b' : 'transparent',
                  color: currency === 'USD' ? '#000000' : '#a8a29e',
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 4,
                  padding: '2px 6px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                USD
              </button>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 12 }}>
            <span style={{ fontSize: 24, fontWeight: 800, color: '#10b981', letterSpacing: '-0.02em', fontFamily: 'var(--font-mono)' }}>
              {(() => {
                const idrVal = (benchmarks?.total_idr_delivered && benchmarks.total_idr_delivered > 0)
                  ? benchmarks.total_idr_delivered
                  : Math.round((metrics.cumulative.tokens / 1_000_000) * 5.0 * 16250);
                const usdVal = (benchmarks?.total_usd_delivered && benchmarks.total_usd_delivered > 0)
                  ? benchmarks.total_usd_delivered
                  : Number(((metrics.cumulative.tokens / 1_000_000) * 5.0).toFixed(2));
                return currency === 'IDR'
                  ? `Rp ${idrVal.toLocaleString('id-ID')}`
                  : `$${usdVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
              })()}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="badge badge-emerald" style={{ fontSize: 9, padding: '1px 5px' }}>Free Tier</span>
            <span>Commercial API savings</span>
          </div>
        </div>

        {/* Card 4: Average Latency */}
        <div
          className="glass-card"
          style={{
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            minHeight: 142,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Average Latency (TTFT)</span>
            <span className="badge badge-emerald">Optimal</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.latency_ms.ttft_avg || 3121}
            </span>
            <span style={{ fontSize: 12, color: '#78716c' }}>ms</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 8 }}>
            Time to first streaming token
          </div>
        </div>

        {/* Card 5: Cumulative Handled */}
        <div
          className="glass-card"
          style={{
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            minHeight: 142,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Cumulative Handled</span>
            <span className="badge badge-neutral">All-time</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.cumulative.requests.toLocaleString()}
            </span>
            <span style={{ fontSize: 12, color: '#78716c' }}>requests</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 8 }}>
            Cumulative: {metrics.cumulative.tokens.toLocaleString()} tokens
          </div>
        </div>
      </div>


      {/* Token Consumption Breakdown Chart */}
      <TokenChart
        data={chartPoints}
        timeRange={timeRange}
        onTimeRangeChange={onTimeRangeChange}
      />

      {/* Top Token Spenders & Quota Drainers Leaderboard */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
              }}
            >
              <BarChart3 size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
                Top Token Spenders & Quota Drainers
              </h2>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
                Persistent request hit analysis and quota impact scoring
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate('benchmarks')}
            className="btn btn-secondary btn-sm"
            style={{ color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <span>View Full Hit Ledger</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {(!benchmarks || !benchmarks.models || benchmarks.models.length === 0) ? (
          <div
            style={{
              textAlign: 'center',
              padding: '28px 20px',
              color: '#a8a29e',
              fontSize: 13,
              background: 'rgba(255, 255, 255, 0.02)',
              borderRadius: 12,
              border: '1px dashed rgba(168, 162, 158, 0.2)',
            }}
          >
            No request hits recorded yet. Send queries through OpenAI clients or the Prompt Sandbox to generate benchmarks.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {benchmarks.models.slice(0, 4).map((m, idx) => {
              const share = m.token_share_pct;
              const barColor = share > 50 ? '#f59e0b' : share > 20 ? '#3b82f6' : '#10b981';
              return (
                <div key={m.model}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#fafaf9', fontFamily: 'var(--font-mono)' }}>
                        {m.model}
                      </span>
                      {idx === 0 && <span className="badge badge-amber" style={{ fontSize: 10 }}>#1 Spender</span>}
                      {m.quota_impact_score >= 30 && (
                        <span className="badge badge-rose" style={{ fontSize: 10, display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Flame size={10} /> Quota Drainer ({m.quota_impact_score})
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span style={{ fontSize: 12, color: '#a8a29e', fontFamily: 'var(--font-mono)' }}>
                        {m.total_tokens.toLocaleString()} tokens
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: barColor, fontFamily: 'var(--font-mono)', minWidth: 42, textAlign: 'right' }}>
                        {share}%
                      </span>
                    </div>
                  </div>

                  <div style={{ height: 6, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 999, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(100, Math.max(2, share))}%`,
                        height: '100%',
                        background: barColor,
                        borderRadius: 999,
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#78716c', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                    <span>{m.requests_count} hits &bull; Avg Latency: {m.avg_latency_ms}ms</span>
                    <span>Last seen: {m.last_seen_formatted}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Grid: Live Quota Meter & OpenAI Client Gateway */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: 20,
        }}
      >
        {/* Live Quota Meter Card */}
        <div className="glass-card" style={{ padding: '24px 28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
                Live Quota Meter
              </h2>
              <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 2 }}>
                Active limits for {activeAccount?.email || 'current account'}
              </p>
            </div>
            <button
              onClick={onSyncQuota}
              disabled={isSyncing}
              className="btn btn-secondary btn-sm"
            >
              <RefreshCw size={13} style={{ animation: isSyncing ? 'spin 1s linear infinite' : 'none' }} />
              <span>{isSyncing ? 'Syncing...' : 'Sync'}</span>
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {quotaItems.length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '36px 20px',
                  color: '#a8a29e',
                  fontSize: 13,
                  background: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: 12,
                  border: '1px dashed rgba(168, 162, 158, 0.2)',
                }}
              >
                <div>No live quota limits loaded yet for <strong style={{ color: '#ffffff' }}>{activeAccount?.email || 'the active account'}</strong>.</div>
                <div style={{ fontSize: 12, color: '#78716c', marginTop: 4 }}>Click <strong>Sync</strong> above to fetch current quota buckets from Google Antigravity.</div>
              </div>
            ) : (
              quotaItems.map((item, idx) => {
              const pct = item.percentage;
              const barColor = pct > 40 ? '#10b981' : pct > 15 ? '#f59e0b' : '#f43f5e';
              return (
                <div key={idx}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#e7e5e4' }}>
                      {item.label}
                    </span>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: barColor,
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {pct.toFixed(1)}%
                    </span>
                  </div>

                  {/* Progress bar track */}
                  <div
                    style={{
                      height: 6,
                      background: 'rgba(255, 255, 255, 0.08)',
                      borderRadius: 999,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, Math.max(0, pct))}%`,
                        height: '100%',
                        background: barColor,
                        borderRadius: 999,
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#78716c', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                    <span>Bucket: {item.family}</span>
                    <span>Reset: {new Date(item.reset_time).toLocaleString()}</span>
                  </div>
                </div>
              );
            }))}
          </div>
        </div>

        {/* Dual-Protocol Client Gateway Card */}
        <div className="glass-card" style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
                Dual-Protocol Client Gateway
              </h2>
              <div style={{ display: 'flex', gap: 6 }}>
                <span className="badge badge-emerald" style={{ fontSize: 10 }}>OpenAI</span>
                <span className="badge badge-amber" style={{ fontSize: 10 }}>Anthropic</span>
              </div>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', lineHeight: 1.5 }}>
              Native drop-in endpoints for Cursor, OpenCode, Cline, Roo Code, Claude Code CLI, and Continue.dev.
            </p>

            {/* OpenAI URL Display */}
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#10b981', textTransform: 'uppercase' }}>
                  OpenAI Base URL (/v1/chat/completions)
                </label>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  borderRadius: 8,
                  padding: '8px 12px',
                  marginTop: 4,
                }}
              >
                <code style={{ fontSize: 12, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
                  {gatewayUrl}
                </code>
                <button
                  onClick={() => copyToClipboard(gatewayUrl, 'url')}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '3px 8px' }}
                >
                  {copiedUrl ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{copiedUrl ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* Anthropic URL Display */}
            <div style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b', textTransform: 'uppercase' }}>
                  Anthropic Base URL (/v1/messages)
                </label>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(245, 158, 11, 0.25)',
                  borderRadius: 8,
                  padding: '8px 12px',
                  marginTop: 4,
                }}
              >
                <code style={{ fontSize: 12, color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>
                  {anthropicGatewayUrl}
                </code>
                <button
                  onClick={() => copyToClipboard(anthropicGatewayUrl, 'anthropic_url')}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '3px 8px' }}
                >
                  {copiedAnthropicUrl ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{copiedAnthropicUrl ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* API Key Display */}
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: '#78716c', textTransform: 'uppercase' }}>
                Auth API Key
              </label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(168, 162, 158, 0.2)',
                  borderRadius: 8,
                  padding: '8px 12px',
                  marginTop: 4,
                }}
              >
                <code style={{ fontSize: 12, color: '#d6d3d1', fontFamily: 'var(--font-mono)' }}>
                  {apiKey}
                </code>
                <button
                  onClick={() => copyToClipboard(apiKey, 'key')}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '3px 8px' }}
                >
                  {copiedKey ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{copiedKey ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              paddingTop: 14,
              marginTop: 16,
              fontSize: 12,
              color: '#78716c',
            }}
          >
            <span>Protocols: <strong style={{ color: '#d6d3d1' }}>OpenAI (/v1) &bull; Anthropic (/v1/messages)</strong></span>
            <span>Version: <strong style={{ color: '#f59e0b' }}>v1.2.1</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
};
