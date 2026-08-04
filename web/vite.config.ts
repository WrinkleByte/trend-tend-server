import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// See docs/pwa-offline.md for the full offline/PWA design this config
// implements: precached app shell, StaleWhileRevalidate for read-only API
// calls, CacheFirst+expiration for content-addressed attachment blobs, and
// the iOS-specific manifest/meta-tag requirements.
export default defineConfig({
  server: {
    // Backend runs separately (docker compose up, or `uvicorn` directly) —
    // proxied here so the app can call same-origin `/api/v1/...` paths in
    // both dev and the production Docker/nginx setup.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['apple-touch-icon.png'],
      manifest: {
        name: 'MaintainIt',
        short_name: 'MaintainIt',
        description: 'Track maintenance for your home, vehicles, and equipment.',
        start_url: '/',
        display: 'standalone',
        theme_color: '#0f172a',
        background_color: '#ffffff',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        // Sync endpoints are deliberately NOT cached here — Dexie is the
        // offline cache; caching sync responses at the SW layer would be
        // redundant and could serve stale sync cursors (see pwa-offline.md).
        navigateFallbackDenylist: [/^\/api\/v1\/sync\//],
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/attachments\/.*\/blob$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'attachment-blobs',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /\/api\/v1\/(?!sync\/).*/,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'api-read-only' },
          },
        ],
      },
    }),
  ],
})
