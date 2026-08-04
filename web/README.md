# MaintainIt Web

React + Vite frontend for MaintainIt. Serves two roles from one codebase: the connected web UI for a self-hosted backend, and an installable, offline-capable PWA (see [`../docs/pwa-offline.md`](../docs/pwa-offline.md)).

## Setup (Docker — recommended)

`docker compose up` from the repo root brings this up as the `web` service alongside `postgres` and `backend`, with your `web/` directory bind-mounted for hot reload — no local `npm install` needed. See the root [`README.md`](../README.md#quickstart-docker). Its dev-proxy target is set via `VITE_API_PROXY_TARGET` in `docker-compose.yml` (points at the `backend` container directly over the Compose network), not the variable described below.

## Setup (running directly on the host)

```bash
npm install
```

The dev server proxies `/api/...` calls to a backend at `vite.config.ts`'s `apiProxyTarget` — defaults to `http://localhost:8000`. If your backend is published on a different host port (see `BACKEND_HOST_PORT` in the root `docker-compose.yml`/README), add a `web/.env` file:

```
VITE_API_PROXY_TARGET=http://localhost:8010
```

Then, with the backend already running (see [`../backend/README.md`](../backend/README.md) or `docker compose up postgres backend` from the repo root):

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

- `src/features/` — the connected CRUD UI (auth, assets, service history + receipt attachments, reminders, API-token pairing). Calls the backend directly over JWT auth (with auto-refresh) via `src/api/` — deliberately bypasses `src/db`/`src/sync` below, which are for the offline PWA path.
- `src/api/` — hand-written typed client (`client.ts` for auth/fetch plumbing, `types.ts` mirroring the backend's Pydantic response shapes, one file per resource). Could be replaced with a generated client via `openapi-typescript` against the running backend's `/openapi.json` later; hand-written was simpler while the shapes were still moving.
- `src/auth/` — `authStore.ts`, a small Zustand store persisting the JWT access/refresh token pair to localStorage.
- `src/db/` — Dexie (IndexedDB) schema mirroring the backend entities 1:1, plus the outbox and pending-conflict stores the sync engine will use. See [`../docs/architecture.md`](../docs/architecture.md) Section 1.
- `src/sync/` — sync engine and background-sync fallback logic (stubs — implemented in Phase 4 of the roadmap, once the mobile sync protocol is battle-tested). See [`../docs/architecture.md`](../docs/architecture.md) Section 3 and [`../docs/pwa-offline.md`](../docs/pwa-offline.md).
- `vite.config.ts` — dev-proxy target (see Setup above) plus PWA configuration (manifest, Workbox caching strategy) — see `../docs/pwa-offline.md` for the reasoning behind each caching rule.

## Testing the offline/PWA behavior

Desktop Chrome's PWA emulation does **not** reproduce iOS Safari's real constraints (storage eviction, no Background Sync API, no install-prompt event). To verify the offline experience for real:

1. `npm run build && npm run preview` (the service worker only registers against a production build, not `vite dev`).
2. Open the preview URL on an actual iPhone in Safari, add it to the home screen, then test with airplane mode on.
3. See [`../docs/pwa-offline.md`](../docs/pwa-offline.md) for the full verification checklist.
