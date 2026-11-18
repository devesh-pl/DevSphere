import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/projects': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/api/deployment-spring': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/api/auth': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/auth/, '/auth')
      },
      '/api/orchestrator': {
        target: 'http://127.0.0.1:8004',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/orchestrator/, '')
      },
      '/api/deployment': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/deployment/, '')
      },
      '/api/build': {
        target: 'http://127.0.0.1:8006',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/build/, '')
      }
    }
  }
});
