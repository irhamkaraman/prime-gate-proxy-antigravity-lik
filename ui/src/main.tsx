import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './styles/index.css';

// Global secure fetch wrapper: Automatically attaches x-csrf-token from cookie for mutations
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  const [resource, config] = args;
  const options: RequestInit = config ? { ...config } : {};
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const match = document.cookie.match(/(?:^|;\s*)pg_csrf=([^;]+)/);
    if (match && match[1]) {
      const headers = new Headers(options.headers || {});
      if (!headers.has('x-csrf-token')) {
        headers.set('x-csrf-token', decodeURIComponent(match[1]));
      }
      options.headers = headers;
    }
  }
  const response = await originalFetch(resource, options);
  if (
    response.status === 401 &&
    typeof resource === 'string' &&
    resource.startsWith('/api/') &&
    !resource.includes('/api/auth/session')
  ) {
    window.dispatchEvent(new CustomEvent('pg_auth_required'));
  }
  return response;
};

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Failed to find root element');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
