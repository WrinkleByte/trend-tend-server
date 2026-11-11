# Trend & Tend Server

Track maintenance for your home, vehicles, and equipment (lawn mowers, snow blowers, HVAC systems, and more) — service history, recurring reminders, and costs, all in one place.

This repository contains the **open-source backend and web app**, licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0-only). Anyone can run it, study it, change it, and share it — including businesses.

The native iOS and Android apps (sold separately through the App Store and Google Play, and fully usable without a server) are proprietary and not part of this repository. They sync with this server over the protocol described in [`docs/architecture.md`](docs/architecture.md). Developer notes and architectural invariants: [`docs/development.md`](docs/development.md).

## Help and more

- **Product overview and the mobile apps:** [wrinklebyte.com/products](https://wrinklebyte.com/products.html)
- **Common questions:** [Trend & Tend FAQ](https://wrinklebyte.com/trend-tend-faq.html)
- **Get help:** [wrinklebyte.com/help](https://wrinklebyte.com/help.html)
- **Bug reports and feature requests for the server or web app:** [GitHub issues](https://github.com/wrinklebyte/trend-tend-server/issues)
- **How your data is handled:** [Trend & Tend privacy model](https://wrinklebyte.com/trend-tend-privacy.html)
- **Ready-to-run images:** [Docker Hub](https://hub.docker.com/r/wrinklebyte/trend-tend-api) and [GHCR](https://github.com/orgs/wrinklebyte/packages?repo_name=trend-tend-server); see [Self-hosting](#self-hosting-production) below

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
apps to sync with, use one of the two options below, not the development
stack further down. Both run the same server and work on amd64 and arm64
(Raspberry Pi, Apple silicon, most NAS boxes).

### Option 1: one container (quickest)

`wrinklebyte/trend-tend-server` bundles PostgreSQL, the API and the web app:

```bash
docker run -d --name trend-tend --restart unless-stopped \
  -p 8080:8080 \
  -e FRONTEND_URL=http://<your-host>:8080 \
  -v trend-tend:/data \
  wrinklebyte/trend-tend-server
```

Open `FRONTEND_URL` in a browser and create the first account; it becomes
the instance admin. Point the mobile apps at the same address.

- **`FRONTEND_URL`** is the address people use to reach the server. It goes
  into password-reset and invite emails and the mobile pairing code. Use your
  HTTPS address if you put a reverse proxy in front.
- **Everything lives in `/data`**: the database, attachments, and
  `secrets.env`, which holds the database passwords and the login-signing
  key, generated on first start. Nothing listens except port 8080.
- **Back up** by stopping the container and archiving the volume, which
  captures all three together:
  ```bash
  docker stop trend-tend
  docker run --rm -v trend-tend:/data -v "$PWD":/backup alpine \
    tar czf /backup/trend-tend-$(date +%F).tgz -C /data .
  docker start trend-tend
  ```
- **Update**: back up, then `docker pull wrinklebyte/trend-tend-server`,
  remove the container and run the same `docker run` again. Migrations run
  automatically. Pin a version tag (for example `:1.0.1`) instead of the
  default `latest` if you'd rather choose when to update.
- **Settings** such as SMTP are environment variables (the `SMTP_*` names in
  [`.env.prod.example`](.env.prod.example)) or the admin settings page.
- The image runs PostgreSQL 16. If a future release changes that, it will
  say so in its release notes, and the container refuses to start on a
  mismatched database rather than touch it.

### Option 2: separate containers (Docker Compose)

For running PostgreSQL as its own container, which also makes it possible
to manage the database separately, use `docker-compose.prod.yml`:

```bash
cp .env.prod.example .env    # fill in the REQUIRED values (secrets, FRONTEND_URL)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

That pulls the released images (`wrinklebyte/trend-tend-api` and
`wrinklebyte/trend-tend-web` on Docker Hub, for amd64 and arm64) at the
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
`docker-compose.prod.yml`, commit, merge to `main` once CI is green, then
push a tag: `git tag vX.Y.Z && git push github vX.Y.Z`. The
[`Release images`](.github/workflows/release.yml) workflow checks the tag
matches all three versions, builds all three images (API, web, all-in-one)
natively on amd64 and arm64 runners, and publishes them to Docker Hub and GHCR (one-time setup is in that
file's header). `scripts/build-release-images.sh --push` does the same from a
maintainer's machine and remains the manual fallback.

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

## CI

Every pull request and push to `main` runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml): `ruff`, Alembic migrations against an empty database, the full `pytest` suite against Postgres, `oxlint` + type-check + PWA build, a gitleaks secret scan of the full history, REUSE licensing compliance, and `scripts/smoke-test-prod.sh --build`.

### Local git hooks

The same fast checks can also run before you commit or push, so failures show up before CI. `scripts/setup-git-hooks.sh` installs local git hooks (tracked in `.githooks/`, copied into `.git/hooks/` since that directory itself isn't version-controlled) that gate commits/pushes:

```bash
scripts/setup-git-hooks.sh   # one-time, per clone
```

- **`pre-commit`** — fast checks only (`ruff` for backend, `oxlint` + `tsc` for web), scoped to whichever of `backend/`/`web/` you actually staged changes in.
- **`pre-push`** — the full backend `pytest` suite and web `npm run build` (type-check + PWA build), unconditionally, since pushes are much less frequent than commits.

Both prefer the running docker-compose stack, then a local `backend/.venv` / `web/node_modules`, and fail if neither can run the check (set `SKIP_HOOK_TOOLING=1` to accept the risk). Bypass either with `--no-verify` if you really need to; CI still runs everything on the pull request.

## Testing

- **Backend**: `cd backend && pytest` — runs against a real (disposable, auto-created/dropped) PostgreSQL database. See [`backend/README.md`](backend/README.md) for details.
- **Web**: `cd web && npm run build` (type-checks and builds, including the PWA service worker) — see [`web/README.md`](web/README.md) for the offline/PWA-specific verification checklist.

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
