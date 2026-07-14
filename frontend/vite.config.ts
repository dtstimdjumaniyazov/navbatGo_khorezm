import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // SW работает и в dev — чтобы установку можно было показать через ngrok
      devOptions: { enabled: true },
      manifest: {
        name: 'NavbatGo — мастер',
        short_name: 'NavbatGo',
        description: 'Управление записями автосервиса',
        lang: 'ru',
        display: 'standalone',
        start_url: '/',
        theme_color: '#2563eb',
        background_color: '#f3f4f6',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
    }),
  ],
  server: {
    host: true, // слушать на всех интерфейсах (доступ по LAN/ngrok)
    allowedHosts: true, // пускать запросы с ngrok-доменов
  },
});
