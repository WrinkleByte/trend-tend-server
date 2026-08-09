# WrinkleByte Web — Offline & PWA Design

This document covers the offline-capable, installable Progressive Web App (PWA) design for the WrinkleByte web frontend (`web/`). It's split out from the main [`architecture.md`](architecture.md) because it's a distinct, self-contained feature: making the same React web app that self-hosters use as their "connected" admin UI also work as a mobile experience with no internet connection — notably on iOS Safari, which has real, non-obvious constraints that shape several of the decisions below.

## Purpose and dual role

The web app serves two audiences from one codebase:

1. The primary connected web UI for a self-hosted backend — household management, settings, API token generation, full CRUD.
2. An installable, offline-capable PWA — added to a phone's home screen and usable with zero connectivity, syncing changes automatically once connectivity returns.

## App structure

```
web/src/
  main.tsx                       # mounts React app, registers service worker
  app/
    router.tsx                    # React Router route tree
  api/
    client.ts                     # typed fetch wrapper (generated from FastAPI's OpenAPI schema
                                   # via openapi-typescript)
    sync.ts                       # calls the same /sync/pull and /sync/push endpoints as mobile
  db/
    schema.ts                     # Dexie.js schema — IndexedDB tables mirroring backend entities 1:1
    db.ts                         # Dexie instance, versioned schema migrations
    outbox.ts                     # pending-changes table + helpers (mirrors the mobile Outbox)
    conflicts.ts                  # pending_conflicts table access
  sync/
    syncEngine.ts                 # same pull→apply→collect→push→resolve orchestration as mobile
    backgroundSync.ts             # registers Background Sync API tag where supported, falls back
                                   # to foreground/visibility-based sync elsewhere
  features/
    assets/  maintenance-records/  schedules/  attachments/  household-settings/  conflict-review/
  state/
    # TanStack Query for server-state caching (connected-only concerns: settings, invites);
    # Zustand for small client-only UI state (active household, sync status banner).
    # Core synced data lives in Dexie — components read it via live queries (dexie-react-hooks'
    # useLiveQuery), never duplicated into a separate store, to avoid a two-source-of-truth bug.
public/
  manifest.webmanifest
vite.config.ts                    # vite-plugin-pwa config (Workbox under the hood)
```

## State/persistence approach

- **Dexie.js** wraps IndexedDB as the local persistence layer — the browser-world equivalent of the mobile apps' SQLDelight database. Chosen over raw IndexedDB for its ergonomic query API and reactive `useLiveQuery` hook, and over PouchDB because Dexie doesn't impose its own sync/replication protocol — this app's custom sync engine (shared with mobile, see `architecture.md` Section 3) is the single sync implementation across all clients, not a second competing one just for web.
- Local reads/writes always go through Dexie first — write to Dexie + the outbox synchronously, then let `syncEngine` push in the background. Components never wait on network for a write to feel "saved," matching the offline-first requirement even in a connected deployment.
- TanStack Query is used only for genuinely server-only, non-synced concerns (admin/settings actions, invite management) that don't need offline queuing. It is not used for asset/record/schedule data, which flows through Dexie + the sync engine exclusively.

## Service worker strategy (Workbox via `vite-plugin-pwa`)

- **App shell**: precached (`precacheAndRoute`), cache-first, versioned by build hash so updates are atomic and never serve mixed old/new asset versions.
- **API responses**: sync endpoints are deliberately **not** cached by the service worker — Dexie is the offline cache, and caching sync responses at the SW layer would be redundant and could serve stale sync cursors. Static/read-only REST calls (e.g. a settings page) use `StaleWhileRevalidate`.
- **Attachments/images**: `CacheFirst` with an expiration plugin (`workbox-expiration`, e.g. cap at 50MB / 30 days) — safe because attachment blobs are immutable and content-addressed (a changed attachment is a new sha256, hence a new cache key, never a stale hit).
- **Install prompt**: standard `beforeinstallprompt` handling on Chromium/Android. **iOS Safari never fires this event at all** — the app must show its own instructional UI ("tap Share, then Add to Home Screen").

## manifest.webmanifest

Standard fields: `name`, `short_name`, `icons` (192/512), `start_url`, `display: "standalone"`, `theme_color`, `background_color`. iOS also needs separate `apple-touch-icon` link tags and `apple-mobile-web-app-capable` / `apple-mobile-web-app-status-bar-style` meta tags in `index.html`, since Safari does not fully honor the web manifest the way Chromium does.

## Background sync when connectivity returns

- **Chromium-based browsers**: register a Background Sync API tag (`workbox-background-sync`'s `BackgroundSyncPlugin`, or a manual `sync` event listener) so a queued push can complete even if the tab is closed shortly after going offline-then-online.
- **iOS Safari does not support the Background Sync API at all.** Fallback strategy: trigger `syncEngine.run()` on (a) every app foreground/visibility-change event, (b) a `navigator.onLine` transition to true, and (c) a periodic in-app timer while the PWA is foregrounded. An installed-but-backgrounded iOS PWA will **not** silently sync the way a native app or an Android/Chrome PWA can — this needs to be communicated in-app (e.g. a "last synced" indicator), not assumed.

## Known iOS Safari constraints to design around

There's no workaround for these — the product needs to be designed around them, not against them:

- **No Background Sync API, no Periodic Background Sync API.** Sync only happens while the user has the app open (see above).
- **Storage eviction.** Safari enforces a 7-day cap on script-writable storage (localStorage, IndexedDB, Cache API) for sites *not* added to the home screen, if there's been no user interaction with the origin in that window (Intelligent Tracking Prevention). Once genuinely installed via "Add to Home Screen," IndexedDB/Dexie data is exempt from this eviction and persists like a native app's storage — which is exactly why the product should actively nudge users toward the install flow rather than treating "visited the site in Safari" as equivalent to "installed the PWA." Call `navigator.storage.persist()` on load to request best-effort persistent storage regardless.
- **Push notifications.** Not supported in home-screen web apps at all prior to iOS 16.4. From 16.4 onward, Web Push is supported, but only for apps actually added to the home screen (not a regular Safari tab), and only after an explicit user-gesture permission grant — it cannot be silently pre-authorized. Overdue-maintenance reminder notifications on the iOS PWA should be treated as a 16.4+-only, best-effort feature that degrades gracefully (no error, just absent) on older iOS — distinct from the native mobile apps, where local notifications work regardless of OS push-service specifics.
- **No install prompt event** (`beforeinstallprompt` never fires) — requires custom in-app instructional UI, as noted above.
- **Conservative storage quota.** WKWebView's storage quota is more conservative than desktop Chrome's; large attachment caching should be capped and evictable (`workbox-expiration`) rather than assumed unlimited.
- **Home screen icon / splash screen.** Requires explicit `apple-touch-icon` and (for a nicer launch experience) `apple-touch-startup-image` tags — the manifest's `icons` array alone is insufficient for full Safari fidelity.

## Verification

- Install to an actual iOS Safari home screen (not just desktop Chrome's PWA emulation, which doesn't reproduce Safari's constraints).
- Enable airplane mode, perform CRUD across all entity types, restore connectivity, verify sync reconciliation completes correctly (including a forced conflict scenario in both LWW and manual-review modes).
- Leave the installed PWA untouched for several days to confirm storage persistence (not evicted) once actually installed to the home screen, versus a plain bookmarked tab (which should show the 7-day eviction behavior, confirming the distinction is real and worth the in-app install nudge).
- Confirm the custom "Add to Home Screen" instructional UI appears on iOS Safari and that the standard install banner appears on Chromium/Android, and that neither path is silently broken on the other platform.
