import React, { createContext, useContext, useState, useCallback } from 'react';
import { ToastItem, ToastType } from '../types';

interface ToastContextValue {
  toasts: ToastItem[];
  showToast: (toast: Omit<ToastItem, 'id'> | string, type?: ToastType) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const showToast = useCallback((toast: Omit<ToastItem, 'id'> | string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    let item: ToastItem;

    if (typeof toast === 'string') {
      item = {
        id,
        type,
        title: toast,
        duration: 4000,
      };
    } else {
      item = {
        ...toast,
        id,
        duration: toast.duration ?? 4000,
      };
    }

    setToasts(prev => [...prev.slice(-4), item]);

    if (item.duration && item.duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, item.duration);
    }
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
