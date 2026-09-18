import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Усі запити до бекенда йдуть через gateway, ніколи напряму в сервіс.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
