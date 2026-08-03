# MaintainIt

Track maintenance for your home, vehicles, and equipment (lawn mowers, snow blowers, HVAC systems, and more) — service history, recurring reminders, and costs, all in one place.

This repository contains the **open-source backend and web app**. It is free for personal, non-commercial use. Business use requires a separate commercial license — see [LICENSE](LICENSE).

Native iOS and Android apps (sold separately, fully standalone-capable with optional sync to a self-hosted instance of this backend) live in a companion private repository (`maintainit-mobile`). See that repo's [`docs/ios-build-and-test.md`](../ios/docs/ios-build-and-test.md) for the mobile build/test guide.

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

## Quickstart (Docker)

The fastest way to get the full stack running locally:

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

This brings up PostgreSQL and the backend API (applying migrations automatically on start) at `http://localhost:8000`. Confirm it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Then run the web app separately (it isn't containerized in this scaffold):

```bash
cd web
npm install
npm run dev
```

## Manual setup (without Docker for the backend)

See [`backend/README.md`](backend/README.md) for running the API directly against a local Postgres, and [`web/README.md`](web/README.md) for the web app. Both READMEs also cover running the test suites.

## Testing

- **Backend**: `cd backend && pytest` — runs against a real (disposable, auto-created/dropped) PostgreSQL database. See [`backend/README.md`](backend/README.md) for details.
- **Web**: `cd web && npm run build` (type-checks and builds, including the PWA service worker) — see [`web/README.md`](web/README.md) for the offline/PWA-specific verification checklist.
- **Mobile**: see the companion `maintainit-mobile` repo's [`docs/ios-build-and-test.md`](../ios/docs/ios-build-and-test.md) and `BUILD.md`.

## Verified status

As of this scaffold: the backend's Alembic migration applies cleanly to Postgres, its full pytest suite passes, and the live server responds correctly over HTTP. The web app type-checks and builds successfully, including PWA artifacts (service worker, manifest). The mobile (`maintainit-mobile`) Kotlin/Swift source has **not** been compiler-verified — it requires a Mac with Xcode and a JDK 17+ / Android SDK toolchain not available in the environment this was scaffolded in. See that repo's `BUILD.md` for what's outstanding.

## License

See [LICENSE](LICENSE). Free for personal use; business/commercial use requires a paid license — contact the author.
