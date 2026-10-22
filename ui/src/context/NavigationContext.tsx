import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { RoutePath } from '../types';

interface NavigationContextValue {
  currentRoute: RoutePath;
  navigate: (route: RoutePath) => void;
}

const NavigationContext = createContext<NavigationContextValue | undefined>(undefined);

function parsePathFromLocation(): RoutePath {
  const hash = window.location.hash.replace('#', '').replace('/', '').trim();
  if (['dashboard', 'benchmarks', 'caching', 'accounts', 'sandbox', 'keys', 'sentinel', 'docs'].includes(hash)) {
    return hash as RoutePath;
  }

  const path = window.location.pathname.replace('/', '').trim().toLowerCase();
  if (['dashboard', 'benchmarks', 'caching', 'accounts', 'sandbox', 'keys', 'sentinel', 'docs'].includes(path)) {
    return path as RoutePath;
  }

  return 'dashboard';
}

export const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentRoute, setCurrentRoute] = useState<RoutePath>(() => parsePathFromLocation());

  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(parsePathFromLocation());
    };

    window.addEventListener('popstate', handlePopState);
    window.addEventListener('hashchange', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('hashchange', handlePopState);
    };
  }, []);

  const navigate = useCallback((route: RoutePath) => {
    setCurrentRoute(route);
    const targetUrl = `/${route}`;
    if (window.location.pathname !== targetUrl) {
      window.history.pushState({ route }, '', targetUrl);
    }
  }, []);

  return (
    <NavigationContext.Provider value={{ currentRoute, navigate }}>
      {children}
    </NavigationContext.Provider>
  );
};

export const useNavigation = (): NavigationContextValue => {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
};
