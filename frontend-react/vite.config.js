import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';

const gatewayTarget = process.env.VITE_AUTH_PROXY_TARGET
  || process.env.VITE_GATEWAY_URL
  || 'http://localhost:3001';
const apiTarget = process.env.VITE_API_PROXY_TARGET
  || process.env.VITE_BACKEND_URL
  || 'http://localhost:8000';
const wsTarget = process.env.VITE_WS_PROXY_TARGET
  || process.env.VITE_BACKEND_WS_URL
  || 'ws://localhost:8000';

export default defineConfig({
  plugins: [
    react(),
    wasm(),
    topLevelAwait(),
  ],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api/v1/auth': {
        target: gatewayTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1/, ''),
      },
      '/api/auth': {
        target: gatewayTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/auth': {
        target: gatewayTarget,
        changeOrigin: true,
      },
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    target: 'esnext',
  },
  optimizeDeps: {
    exclude: ['groupbuy-wasm'],
  },
});
