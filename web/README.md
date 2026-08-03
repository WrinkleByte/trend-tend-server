# MaintainIt Web

React + Vite frontend for MaintainIt. Serves two roles from one codebase: the connected web UI for a self-hosted backend, and an installable, offline-capable PWA (see [`../docs/pwa-offline.md`](../docs/pwa-offline.md)).

## Setup

```bash
npm install
```

The dev server proxies API calls to a backend — start the backend first (see [`../backend/README.md`](../backend/README.md) or run `docker compose up` from the repo root), then:

```bash
npm run dev
```

## Build

```bash
npm run build
```

This runs `tsc -b` (type-check) followed by `vite build`, and generates the PWA service worker (`dist/sw.js`) and web manifest via `vite-plugin-pwa`. Output goes to `dist/`.

## Type-check only

```bash
npx tsc -b
```

## Lint

```bash
npm run lint
```

## Project layout

- `src/db/` — Dexie (IndexedDB) schema mirroring the backend entities 1:1, plus the outbox and pending-conflict stores used by the sync engine. See [`../docs/architecture.md`](../docs/architecture.md) Section 1.
- `src/sync/` — sync engine and background-sync fallback logic (stubs — implemented in Phase 4 of the roadmap, once the mobile sync protocol is battle-tested). See [`../docs/architecture.md`](../docs/architecture.md) Section 3 and [`../docs/pwa-offline.md`](../docs/pwa-offline.md).
- `src/api/` — typed API client. Currently hand-written; replace with a generated client via `openapi-typescript` against the running backend's `/openapi.json` once the connected-CRUD UI is built out.
- `vite.config.ts` — PWA configuration (manifest, Workbox caching strategy) — see `../docs/pwa-offline.md` for the reasoning behind each caching rule.

## Testing the offline/PWA behavior

Desktop Chrome's PWA emulation does **not** reproduce iOS Safari's real constraints (storage eviction, no Background Sync API, no install-prompt event). To verify the offline experience for real:

1. `npm run build && npm run preview` (the service worker only registers against a production build, not `vite dev`).
2. Open the preview URL on an actual iPhone in Safari, add it to the home screen, then test with airplane mode on.
3. See [`../docs/pwa-offline.md`](../docs/pwa-offline.md) for the full verification checklist.
