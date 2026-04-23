import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Serve from /admin-panel/ sub-path so all asset URLs are prefixed correctly
  base: '/admin-panel/',
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api/admin': {
        target: 'http://localhost:4010',
        changeOrigin: true,
      },
    },
  },
})
