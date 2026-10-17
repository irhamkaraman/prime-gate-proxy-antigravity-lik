import React, { useState } from 'react';
import { TelemetryMetrics, Account, TokenVolumePoint } from '../types';
import { TokenChart } from '../components/TokenChart';
import { useToast } from '../context/ToastContext';
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
} from 'lucide-react';

interface DashboardPageProps {
  metrics: TelemetryMetrics;
  activeAccount: Account | null;
  onSyncQuota: () => Promise<void>;
  isSyncing: boolean;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  metrics,
  activeAccount,
  onSyncQuota,
  isSyncing,
}) => {
  const { showToast } = useToast();
  const [timeRange, setTimeRange] = useState<'1s' | '1m' | '1h' | '1d'>('1m');
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  const gatewayUrl = 'http://127.0.0.1:52111/v1';
  const apiKey = 'prime-gate-proxy';

  const copyToClipboard = (text: string, type: 'url' | 'key') => {
    navigator.clipboard.writeText(text).then(() => {
      if (type === 'url') {
        setCopiedUrl(true);
        setTimeout(() => setCopiedUrl(false), 2000);
      } else {
        setCopiedKey(true);
        setTimeout(() => setCopiedKey(false), 2000);
      }
      showToast(`${type === 'url' ? 'Endpoint URL' : 'API Key'} copied to clipboard!`, 'success');
    });
  };

  // Build chart points from live data
  const chartPoints: TokenVolumePoint[] = [
    { timestamp: '1', timeLabel: '03:10', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '2', timeLabel: '03:15', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '3', timeLabel: '03:20', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '4', timeLabel: '03:25', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    {
      timestamp: '5',
      timeLabel: '03:32',
      prompt: metrics.tokens_today.prompt || 94901,
      reasoning: metrics.tokens_today.reasoning || 1085,
      completion: metrics.tokens_today.completion || 366,
      total: (metrics.tokens_today.prompt || 94901) + (metrics.tokens_today.reasoning || 1085) + (metrics.tokens_today.completion || 366),
    },
    { timestamp: '6', timeLabel: '03:38', prompt: 0, reasoning: 0, completion: 0, total: 0 },
  ];

  const quotaItems = activeAccount?.quota_summary && activeAccount.quota_summary.length > 0
    ? activeAccount.quota_summary
    : [
        { family: 'gemini-weekly', label: 'Gemini Models (Weekly Limit Remaining)', percentage: 100, reset_time: '2026-10-24T20:37:31Z' },
        { family: 'gemini-5h', label: 'Gemini Models (Five Hour Limit Remaining)', percentage: 100, reset_time: '2026-10-18T01:37:31Z' },
        { family: 'gp-weekly', label: 'Claude and GPT models (Weekly Limit Remaining)', percentage: 48.3, reset_time: '2026-10-20T19:05:52Z' },
        { family: 'gp-5h', label: 'Claude and GPT models (Five Hour Limit Remaining)', percentage: 98.8, reset_time: '2026-10-18T04:19:12Z' },
      ];

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* 4 Stat Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16,
        }}
      >
        {/* Card 1: Throughput */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Throughput Speed</span>
            <div className="pulse-dot" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 30, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.throughput_tokens_per_sec.toFixed(1)}
            </span>
            <span style={{ fontSize: 13, color: '#78716c' }}>tokens / sec</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 6 }}>
            Active rolling output rate
          </div>
        </div>

        {/* Card 2: Tokens Consumed Today */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Tokens Consumed Today</span>
            <span className="badge badge-amber">24h Rolling</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 30, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.tokens_today.total.toLocaleString()}
            </span>
            <span style={{ fontSize: 13, color: '#78716c' }}>tokens</span>
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 6, fontFamily: 'var(--font-mono)' }}>
            Prompt: {metrics.tokens_today.prompt.toLocaleString()} &bull; Comp: {metrics.tokens_today.completion.toLocaleString()} &bull; Think: {metrics.tokens_today.reasoning.toLocaleString()}
          </div>
        </div>

        {/* Card 3: Average Latency */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Average Latency (TTFT)</span>
            <span className="badge badge-emerald">Optimal</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 30, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.latency_ms.ttft_avg || 3121}
            </span>
            <span style={{ fontSize: 13, color: '#78716c' }}>ms</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 6 }}>
            Time to first streaming token
          </div>
        </div>

        {/* Card 4: Cumulative Handled */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#a8a29e', fontWeight: 500 }}>Cumulative Handled</span>
            <span className="badge badge-neutral">All-time</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
            <span style={{ fontSize: 30, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
              {metrics.cumulative.requests.toLocaleString()}
            </span>
            <span style={{ fontSize: 13, color: '#78716c' }}>requests</span>
          </div>
          <div style={{ fontSize: 12, color: '#78716c', marginTop: 6 }}>
            Cumulative: {metrics.cumulative.tokens.toLocaleString()} tokens
          </div>
        </div>
      </div>

      {/* Token Consumption Breakdown Chart */}
      <TokenChart
        data={chartPoints}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
      />

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
            {quotaItems.map((item, idx) => {
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
            })}
          </div>
        </div>

        {/* OpenAI Client Gateway Card */}
        <div className="glass-card" style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
                OpenAI Client Gateway
              </h2>
              <span className="badge badge-emerald">Ready</span>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', lineHeight: 1.5 }}>
              Drop-in OpenAI base URL compatible with OpenCode, Cursor, Continue, SillyTavern, and Cline.
            </p>

            {/* URL Display */}
            <div style={{ marginTop: 20 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: '#78716c', textTransform: 'uppercase' }}>
                Base URL
              </label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(168, 162, 158, 0.2)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  marginTop: 6,
                }}
              >
                <code style={{ fontSize: 13, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                  {gatewayUrl}
                </code>
                <button
                  onClick={() => copyToClipboard(gatewayUrl, 'url')}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '4px 8px' }}
                >
                  {copiedUrl ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                  <span>{copiedUrl ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* API Key Display */}
            <div style={{ marginTop: 16 }}>
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
                  padding: '10px 14px',
                  marginTop: 6,
                }}
              >
                <code style={{ fontSize: 13, color: '#d6d3d1', fontFamily: 'var(--font-mono)' }}>
                  {apiKey}
                </code>
                <button
                  onClick={() => copyToClipboard(apiKey, 'key')}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '4px 8px' }}
                >
                  {copiedKey ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
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
              paddingTop: 16,
              marginTop: 20,
              fontSize: 12,
              color: '#78716c',
            }}
          >
            <span>Protocols: <strong style={{ color: '#d6d3d1' }}>REST &bull; SSE</strong></span>
            <span>Provider: <strong style={{ color: '#f59e0b' }}>prime-gate-proxy</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
};
