import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Legacy alias: the bundled SPA posts to /auth/register and
      // /auth/login. Vite's connect-style dev server has no POST handler,
      // so unproxied /auth/* requests return "Cannot POST /auth/register".
      // Forward /auth/* unchanged to the backend.
      '/auth': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
