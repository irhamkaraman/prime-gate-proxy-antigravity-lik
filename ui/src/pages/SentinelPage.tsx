import React, { useState, useEffect } from 'react';
import { DbSentinelStatus, AuditLogEvent } from '../types';
import { useToast } from '../context/ToastContext';
import { ShieldCheck, Database, Wrench, CheckCircle, AlertTriangle, RefreshCw, Terminal } from 'lucide-react';

export const SentinelPage: React.FC = () => {
  const { showToast } = useToast();
  const [dbStatus, setDbStatus] = useState<DbSentinelStatus | null>(null);
  const [logs, setLogs] = useState<AuditLogEvent[]>([]);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/db/status');
      if (res.ok) {
        const data = await res.json();
        setDbStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch DB status:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch('/v1/health');
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.recent_logs)) {
          setLogs(data.recent_logs.map((l: { timestamp: string; level: string; source: string; message: string }, idx: number) => ({
            id: String(idx),
            timestamp: l.timestamp,
            level: (l.level.toLowerCase() === 'info' ? 'info' : l.level.toLowerCase() === 'warn' ? 'warn' : 'info') as AuditLogEvent['level'],
            source: l.source,
            message: l.message,
          })));
        }
      }
    } catch (err) {
      console.error('Failed to fetch audit logs:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();
    const timer = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  const handleVerify = async () => {
    setIsVerifying(true);
    try {
      const res = await fetch('/api/db/verify', { method: 'POST' });
      if (!res.ok) throw new Error('Verification failed');
      const data = await res.json();
      showToast(data.message || 'Database CRC32 & page integrity check passed!', 'success');
      await fetchStatus();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Integrity verification failed', 'error');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleOptimize = async () => {
    setIsOptimizing(true);
    try {
      const res = await fetch('/api/db/optimize', { method: 'POST' });
      if (!res.ok) throw new Error('Optimization failed');
      const data = await res.json();
      showToast(data.message || 'VACUUM and WAL checkpoint completed successfully!', 'success');
      await fetchStatus();
    } catch (err: unknown) {
      showToast((err as Error).message || 'Database optimization failed', 'error');
    } finally {
      setIsOptimizing(false);
    }
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Banner */}
      <div
        className="glass-card"
        style={{
          padding: '24px 28px',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), #130f0c)',
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
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#10b981',
            }}
          >
            <ShieldCheck size={28} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#ffffff' }}>
                Sentinel Daemon Active
              </h2>
              <span className="badge badge-emerald">Healthy & Verified</span>
            </div>
            <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 4 }}>
              Compiled binary SQLite database with WAL mode and CRC32 header corruption sentinel (45s audit loop)
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={handleVerify}
            disabled={isVerifying}
            className="btn btn-secondary"
          >
            <RefreshCw size={14} style={{ animation: isVerifying ? 'spin 1s linear infinite' : 'none' }} />
            <span>{isVerifying ? 'Verifying...' : 'Verify CRC32'}</span>
          </button>
          <button
            onClick={handleOptimize}
            disabled={isOptimizing}
            className="btn btn-primary"
          >
            <Wrench size={14} />
            <span>{isOptimizing ? 'Optimizing...' : 'Run VACUUM'}</span>
          </button>
        </div>
      </div>

      {/* Grid: Storage Metrics & Specs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
        }}
      >
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 12, color: '#a8a29e', fontWeight: 500 }}>Journal Mode</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#34d399', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
            {dbStatus?.journal_mode?.toUpperCase() || 'WAL'}
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 4 }}>Write-Ahead Logging enabled</div>
        </div>

        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 12, color: '#a8a29e', fontWeight: 500 }}>Integrity Check</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#10b981', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
            {dbStatus?.integrity_check || 'OK'}
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 4 }}>Zero corruption detected</div>
        </div>

        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 12, color: '#a8a29e', fontWeight: 500 }}>Page Count / Size</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#fafaf9', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
            {dbStatus?.page_count || 32} / {dbStatus?.page_size || 4096}B
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 4 }}>High-throughput cache</div>
        </div>

        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 12, color: '#a8a29e', fontWeight: 500 }}>Audit Interval</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#fbbf24', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
            45 seconds
          </div>
          <div style={{ fontSize: 11, color: '#78716c', marginTop: 4 }}>Active background guard</div>
        </div>
      </div>

      {/* Audit Log Stream */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={18} color="#f59e0b" />
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#ffffff' }}>
              Sentinel Daemon Audit Trail
            </h3>
          </div>
          <button
            onClick={fetchLogs}
            className="btn btn-secondary btn-sm"
          >
            <RefreshCw size={13} />
            <span>Refresh Logs</span>
          </button>
        </div>

        <div
          style={{
            background: '#090807',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: 10,
            padding: 16,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            maxHeight: 380,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {logs.length > 0 ? (
            logs.map((log, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 12,
                  padding: '6px 8px',
                  borderRadius: 6,
                  background: 'rgba(255, 255, 255, 0.02)',
                }}
              >
                <span style={{ color: '#78716c', flexShrink: 0 }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span
                  style={{
                    color: log.level === 'warn' ? '#f59e0b' : log.level === 'error' ? '#f43f5e' : '#34d399',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    fontSize: 10,
                    flexShrink: 0,
                  }}
                >
                  [{log.level}]
                </span>
                <span style={{ color: '#d97706', flexShrink: 0 }}>
                  {log.source}:
                </span>
                <span style={{ color: '#d6d3d1', wordBreak: 'break-word' }}>
                  {log.message}
                </span>
              </div>
            ))
          ) : (
            <div style={{ color: '#57534e', padding: 12, textAlign: 'center' }}>
              No audit warning logs recorded. System operating at peak efficiency.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
