import React, { useState } from 'react';
import { Account } from '../types';
import { useToast } from '../context/ToastContext';
import { useModal } from '../context/ModalContext';
import {
  UserPlus,
  Trash2,
  ArrowRightLeft,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Copy,
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
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null);
  const [deletingEmail, setDeletingEmail] = useState<string | null>(null);

  const handleSwitchAccount = async (email: string) => {
    try {
      setSwitchingEmail(email);
      const res = await fetch(`/api/accounts/switch?email=${encodeURIComponent(email)}`, {
        method: 'POST',
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
    </div>
  );
};
