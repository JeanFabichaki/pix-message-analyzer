import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    watch: {
      usePolling: true,
    },
    proxy: {
      '/pix-api': {
        target: process.env.VITE_GATEWAY_URL || 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/pix-api/, ''),
      },
      '/user-api': {
        target: process.env.VITE_USER_SERVICE_URL || 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/user-api/, ''),
      },
      '/gemini-api': {
        target: process.env.VITE_GEMINI_AGENT_URL || 'http://localhost:8003',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/gemini-api/, ''),
      },
      '/threat-intel-api': {
        target: process.env.VITE_THREAT_INTEL_URL || 'http://localhost:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/threat-intel-api/, ''),
      },
    },
  },
});
