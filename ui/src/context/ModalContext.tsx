import React, { createContext, useContext, useState, useCallback } from 'react';
import { ModalConfig } from '../types';

interface ModalContextValue {
  modalConfig: ModalConfig | null;
  openModal: (config: Omit<ModalConfig, 'isOpen'>) => void;
  closeModal: () => void;
  confirmAction: (options: {
    title: string;
    description: string;
    confirmText?: string;
    confirmVariant?: 'primary' | 'danger' | 'warning';
    onConfirm: () => Promise<void> | void;
  }) => void;
}

const ModalContext = createContext<ModalContextValue | undefined>(undefined);

export const ModalProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [modalConfig, setModalConfig] = useState<ModalConfig | null>(null);

  const closeModal = useCallback(() => {
    setModalConfig(null);
  }, []);

  const openModal = useCallback((config: Omit<ModalConfig, 'isOpen'>) => {
    setModalConfig({
      ...config,
      isOpen: true,
      onCancel: () => {
        config.onCancel?.();
        setModalConfig(null);
      },
    });
  }, []);

  const confirmAction = useCallback((options: {
    title: string;
    description: string;
    confirmText?: string;
    confirmVariant?: 'primary' | 'danger' | 'warning';
    onConfirm: () => Promise<void> | void;
  }) => {
    openModal({
      title: options.title,
      description: options.description,
      confirmText: options.confirmText ?? 'Confirm',
      confirmVariant: options.confirmVariant ?? 'primary',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          await options.onConfirm();
          setModalConfig(null);
        } catch (err) {
          console.error('Modal action failed:', err);
        }
      },
      onCancel: () => setModalConfig(null),
    });
  }, [openModal]);

  return (
    <ModalContext.Provider value={{ modalConfig, openModal, closeModal, confirmAction }}>
      {children}
    </ModalContext.Provider>
  );
};

export const useModal = (): ModalContextValue => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
};
