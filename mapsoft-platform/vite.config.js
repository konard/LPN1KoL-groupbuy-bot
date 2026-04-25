import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  publicDir: false,
  build: {
    outDir: 'public/build',
    emptyOutDir: true,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
});
