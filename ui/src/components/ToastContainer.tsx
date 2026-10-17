import React from 'react';
import { useToast } from '../context/ToastContext';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';
import { ToastType } from '../types';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  const getIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 size={18} className="toast-icon text-emerald" style={{ color: '#10b981' }} />;
      case 'error':
        return <XCircle size={18} className="toast-icon text-rose" style={{ color: '#f43f5e' }} />;
      case 'warning':
        return <AlertTriangle size={18} className="toast-icon text-amber" style={{ color: '#f59e0b' }} />;
      case 'info':
      default:
        return <Info size={18} className="toast-icon text-sky" style={{ color: '#38bdf8' }} />;
    }
  };

  const getBorderColor = (type: ToastType) => {
    switch (type) {
      case 'success': return 'rgba(16, 185, 129, 0.35)';
      case 'error': return 'rgba(244, 63, 94, 0.4)';
      case 'warning': return 'rgba(245, 158, 11, 0.4)';
      case 'info': return 'rgba(56, 189, 248, 0.35)';
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        maxWidth: 420,
        width: 'calc(100vw - 40px)',
        pointerEvents: 'none',
      }}
    >
      {toasts.map(toast => (
        <div
          key={toast.id}
          className="animate-fade-in"
          style={{
            pointerEvents: 'auto',
            background: '#181310',
            border: `1px solid ${getBorderColor(toast.type)}`,
            borderRadius: 12,
            padding: '12px 16px',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.6)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            backdropFilter: 'blur(8px)',
          }}
        >
          <div style={{ marginTop: 2 }}>{getIcon(toast.type)}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#fafaf9', lineHeight: 1.4 }}>
              {toast.title}
            </div>
            {toast.message && (
              <div style={{ fontSize: 12, color: '#a8a29e', marginTop: 3, lineHeight: 1.4 }}>
                {toast.message}
              </div>
            )}
          </div>
          <button
            onClick={() => removeToast(toast.id)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#78716c',
              cursor: 'pointer',
              padding: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
            }}
            aria-label="Close notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
};
