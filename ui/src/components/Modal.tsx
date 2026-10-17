import React, { useEffect } from 'react';
import { useModal } from '../context/ModalContext';
import { X, AlertCircle } from 'lucide-react';

export const Modal: React.FC = () => {
  const { modalConfig, closeModal } = useModal();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && modalConfig?.isOpen) {
        closeModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalConfig, closeModal]);

  if (!modalConfig || !modalConfig.isOpen) return null;

  const isDanger = modalConfig.confirmVariant === 'danger';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9998,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeModal();
      }}
    >
      <div
        className="animate-fade-in"
        style={{
          background: '#15110e',
          border: '1px solid rgba(168, 162, 158, 0.2)',
          borderRadius: 16,
          maxWidth: 500,
          width: '100%',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {isDanger && <AlertCircle size={20} color="#f43f5e" />}
            <h3 style={{ fontSize: 17, fontWeight: 700, color: '#fafaf9' }}>
              {modalConfig.title}
            </h3>
          </div>
          <button
            onClick={closeModal}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#78716c',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 6,
              display: 'flex',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '24px', overflowY: 'auto', maxHeight: '70vh' }}>
          {modalConfig.description && (
            <p style={{ fontSize: 14, color: '#a8a29e', lineHeight: 1.6, marginBottom: modalConfig.content ? 16 : 0 }}>
              {modalConfig.description}
            </p>
          )}
          {modalConfig.content}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            background: '#110d0a',
            borderTop: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 12,
          }}
        >
          {modalConfig.cancelText && (
            <button
              onClick={closeModal}
              className="btn btn-secondary"
            >
              {modalConfig.cancelText}
            </button>
          )}
          {modalConfig.onConfirm && (
            <button
              onClick={() => modalConfig.onConfirm?.()}
              className={`btn ${isDanger ? 'btn-danger' : 'btn-primary'}`}
            >
              {modalConfig.confirmText || 'Confirm'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
