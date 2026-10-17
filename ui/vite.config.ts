import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 52110,
    strictPort: true,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:52111',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://127.0.0.1:52111',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:52111',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:52111',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
});
