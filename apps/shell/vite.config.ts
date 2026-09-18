import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // У дев-режимі роль gateway виконує цей проксі: маршрутизує за першим
      // сегментом шляху і зрізає /api. Кожен новий блок додає сюди рядок,
      // поки не з'явиться справжній gateway на :8000.
      '/api/customers': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
