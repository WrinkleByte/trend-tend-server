# WrinkleByte

Track maintenance for your home, vehicles, and equipment (lawn mowers, snow blowers, HVAC systems, and more) — service history, recurring reminders, and costs, all in one place.

This repository contains the **open-source backend and web app**, licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0-only). Anyone can run it, study it, change it, and share it — including businesses.

Native iOS and Android apps (sold separately, fully standalone-capable with optional sync to a self-hosted instance of this backend) live in a companion private repository (`tendfida-mobile`). See that repo's [`docs/ios-build-and-test.md`](../tendfida-mobile/docs/ios-build-and-test.md) for the mobile build/test guide.

## Repository layout

- `backend/` — FastAPI + PostgreSQL API server
- `web/` — React + Vite web app (also an installable offline-capable PWA)
- `docs/` — architecture and design documentation
  - [`docs/architecture.md`](docs/architecture.md) — full system architecture
  - [`docs/pwa-offline.md`](docs/pwa-offline.md) — offline/PWA design for the mobile web experience

## Prerequisites

- **Docker** and **Docker Compose** (recommended path — see Quickstart below), **or**
- **Python 3.11+** and a local **PostgreSQL 16** for running the backend outside Docker
- **Node.js 20+** for the web app

## Self-hosting (production)

To actually run an instance, for yourself, your household, or the mobile
apps to sync with, use `docker-compose.prod.yml`, not the development
stack below:

```bash
cp .env.prod.example .env    # fill in the REQUIRED values (secrets, FRONTEND_URL)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

That pulls the released images (`wrinklebyte/wrinklebyte-backend` and
`wrinklebyte/wrinklebyte-web` on Docker Hub, for amd64 and arm64) at the
version pinned by `WRINKLEBYTE_VERSION`. The identical images are also on
the GitHub Container Registry; to pull from there instead, set
`WRINKLEBYTE_IMAGE_PREFIX=ghcr.io/wrinklebyte` in `.env`. To build from this
source tree instead, use `up -d --build`.

- **One port.** The web container (`WEB_HOST_PORT`, default 8080) serves the
  app and proxies `/api/` to the backend on the same origin. Postgres and the
  backend aren't published at all. Point the mobile apps at the same URL as
  the web app.
- **No default secrets.** Compose refuses to start until `POSTGRES_PASSWORD`,
  `APP_DB_PASSWORD`, `JWT_SECRET` and `FRONTEND_URL` are set, and the
  backend refuses a JWT secret shorter than 32 bytes.
- **Hardened images** (`backend/Dockerfile.prod`, `web/Dockerfile.prod`):
  non-root, no dev dependencies, read-only root filesystems. Migrations run
  automatically on each backend start.
- **Data** lives in two named volumes, `postgres_data` and
  `attachments_data`. Back up both.
- **TLS:** put a reverse proxy (Caddy, Traefik, a Cloudflare tunnel, ...) in
  front for anything reachable beyond your LAN. The stack itself speaks
  plain HTTP.
- The first account registered becomes the instance admin (see
  [Administering a self-hosted instance](#administering-a-self-hosted-instance)).
  Set up that account straight after first start, or turn off
  self-registration afterwards.

Updating: back up both volumes, set `WRINKLEBYTE_VERSION` in `.env` to the
new release, then `pull` and `up -d` again (or `git pull` and `up -d --build`
when building from source). `GET /health` on the backend reports the version
that is actually running.

**Releasing (maintainers):** bump the version in `backend/pyproject.toml`,
`web/package.json` and the `WRINKLEBYTE_VERSION` default in
`docker-compose.prod.yml`, commit, then run `scripts/smoke-test-prod.sh --build`
followed by `scripts/build-release-images.sh --push`.

## Quickstart (Docker, local development)

The fastest way to get the full stack running locally for development. This
stack uses published default passwords, `DEV_MODE`, and source bind-mounts
with hot reload, so **don't expose it beyond your own machine**. Use the
production stack above for that.

```bash
cp .env.example .env    # optional: only needed to change ports or set SMTP
docker compose up --build
```

This brings up PostgreSQL, the backend API (applying migrations automatically on start), and the web app's dev server:

- Backend: `http://localhost:8000`
- Web app: `http://localhost:5173`

Confirm the backend's up:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

If port 8000 or 5173 is already taken on your machine, add `BACKEND_HOST_PORT=<port>` and/or `WEB_HOST_PORT=<port>` to a root `.env` file (Compose reads it automatically) — containers still listen on their normal ports internally, only the host-side mapping changes.

The `web` container runs Vite's dev server with your `web/` directory bind-mounted, so edits on the host hot-reload inside the container — there's no separate `npm install`/`npm run dev` step needed for the Docker path. It proxies `/api/...` to the `backend` container directly over the Compose network (`VITE_API_PROXY_TARGET`, set in `docker-compose.yml`), independent of whatever `BACKEND_HOST_PORT` you chose.

To run the web app directly on the host instead (outside Docker), see [`web/README.md`](web/README.md) — it needs `VITE_API_PROXY_TARGET` pointed at the backend's *host* port (via a `web/.env` file) since `localhost` inside a container and `localhost` on your host are different things.

## Manual setup (without Docker for the backend)

See [`backend/README.md`](backend/README.md) for running the API directly against a local Postgres, and [`web/README.md`](web/README.md) for the web app. Both READMEs also cover running the test suites.

## Administering a self-hosted instance

The first account ever registered on an instance automatically becomes its **instance admin** — separate from a household's "owner" role, since one instance can host many independent households but has only one set of instance-wide settings (SMTP relay, and visibility into every household). An instance admin gets an "All households" panel and SMTP config in the web app's Settings page, and can promote other users to instance admin from there too.

Locked out, or need to act before any admin exists? `backend/scripts/reset-password.sh` resets a user's password directly against the database, no email required — see [`backend/README.md`](backend/README.md#admin-operations) for usage and for the direct-database fallback to promote the very first admin on a fresh instance.

## Local CI (git hooks)

This repo isn't pushed to GitHub yet, so there's no Actions-based CI — instead, `scripts/setup-git-hooks.sh` installs local git hooks (tracked in `.githooks/`, copied into `.git/hooks/` since that directory itself isn't version-controlled) that gate commits/pushes:

```bash
scripts/setup-git-hooks.sh   # one-time, per clone
```

- **`pre-commit`** — fast checks only (`ruff` for backend, `oxlint` + `tsc` for web), scoped to whichever of `backend/`/`web/` you actually staged changes in.
- **`pre-push`** — the full backend `pytest` suite and web `npm run build` (type-check + PWA build), unconditionally, since pushes are much less frequent than commits.

Both fall back to a warning (not a failure) if the relevant toolchain isn't set up yet (no `backend/.venv`, no `web/node_modules`) rather than blocking you outright. Bypass either with `--no-verify` if you really need to. Once this repo does move to GitHub, the same checks belong in an Actions workflow — the hooks aren't meant to be the permanent answer, just what covers local-only development for now.

## Testing

- **Backend**: `cd backend && pytest` — runs against a real (disposable, auto-created/dropped) PostgreSQL database. See [`backend/README.md`](backend/README.md) for details.
- **Web**: `cd web && npm run build` (type-checks and builds, including the PWA service worker) — see [`web/README.md`](web/README.md) for the offline/PWA-specific verification checklist.
- **Mobile**: see the companion `tendfida-mobile` repo's [`docs/ios-build-and-test.md`](../tendfida-mobile/docs/ios-build-and-test.md) and `BUILD.md`.

## Verified status

As of this scaffold: the backend's Alembic migration applies cleanly to Postgres, its full pytest suite passes, and the live server responds correctly over HTTP. The web app type-checks and builds successfully, including PWA artifacts (service worker, manifest). The mobile (`tendfida-mobile`) Kotlin/Swift source has **not** been compiler-verified — it requires a Mac with Xcode and a JDK 17+ / Android SDK toolchain not available in the environment this was scaffolded in. See that repo's `BUILD.md` for what's outstanding.

## License

Copyright © 2026 WrinkleByte LLC. The backend and web app are licensed
under the **GNU Affero General Public License, version 3 only**
(`AGPL-3.0-only`) — see [LICENSE](LICENSE). In short: you may use, run,
modify, and redistribute this code, including commercially. If you
distribute a modified version, or let other people use a modified
version over a network (for example, as a hosted service), you must make
your modified source code available to them under the same license.

The **names and logos** "WrinkleByte" and "Trend & Tend" are not covered
by the code license — see [TRADEMARKS.md](TRADEMARKS.md). The native
iOS/Android apps are separate, proprietary products and are not part of
this repository.

Contributions are welcome under the terms in
[CONTRIBUTING.md](CONTRIBUTING.md), which require signing the
[Contributor License Agreement](CLA.md).
