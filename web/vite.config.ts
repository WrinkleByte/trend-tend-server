import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// See docs/pwa-offline.md for the full offline/PWA design this config
// implements: precached app shell, StaleWhileRevalidate for read-only API
// calls, CacheFirst+expiration for content-addressed attachment blobs, and
// the iOS-specific manifest/meta-tag requirements.
export default defineConfig(({ mode }) => {
  // The backend proxy target differs by how this dev server itself is
  // running: inside docker-compose it must reach the `backend` service by
  // its Compose network name (docker-compose.yml sets
  // VITE_API_PROXY_TARGET=http://backend:8000 for that case); run directly
  // on the host, it targets whatever host port the backend published (see
  // BACKEND_HOST_PORT in docker-compose.yml/README.md) — override via a
  // VITE_API_PROXY_TARGET entry in web/.env for that case.
  const fileEnv = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget =
    process.env.VITE_API_PROXY_TARGET || fileEnv.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    server: {
      proxy: {
        '/api': apiProxyTarget,
      },
    },
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['apple-touch-icon.png'],
        manifest: {
          name: 'WrinkleByte Tending and Trending',
          short_name: 'WrinkleByte',
          description: 'Track maintenance for your home, vehicles, and equipment.',
          start_url: '/',
          display: 'standalone',
          theme_color: '#0F1B2D',
          background_color: '#0F1B2D',
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
  }
})
