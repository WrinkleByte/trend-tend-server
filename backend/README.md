# WrinkleByte Backend

FastAPI + PostgreSQL API server for WrinkleByte.

## Prerequisites

- Python 3.11+
- A running PostgreSQL 16 instance (via Docker, per below, or your own)

## Local development

```bash
cp .env.example .env
docker compose up postgres -d      # from repo root — starts just Postgres
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`, OpenAPI schema at `/openapi.json`).

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

If port 8000 is already in use on your machine: pass `--port` to `uvicorn` for local (non-Docker) runs, or for `docker compose up`, add `BACKEND_HOST_PORT=<port>` to a root `.env` file — Compose reads it automatically and only the host-side mapping changes (the container still listens on 8000 internally). Update `web/vite.config.ts`'s dev proxy target to match.

### Environment variables

Set in `.env` (see `.env.example` for the full list, defaults shown):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://wrinklebyte:wrinklebyte@localhost:5432/wrinklebyte` | Async SQLAlchemy connection string |
| `JWT_SECRET` | *(dev placeholder)* | HMAC signing key for access/refresh tokens — **generate a real random 32+ byte value for anything beyond local dev** (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token lifetime |
| `STORAGE_BACKEND` | `local_disk` | `local_disk` or `s3` — see `app/storage/` |
| `STORAGE_LOCAL_ROOT` | `./data/attachments` | Only used when `STORAGE_BACKEND=local_disk` |
| `STORAGE_S3_*` | *(empty)* | Bucket/endpoint/credentials — only used when `STORAGE_BACKEND=s3`; works against AWS S3 or any S3-compatible endpoint (MinIO, R2, B2) |

## Database migrations

Schema changes are managed exclusively through Alembic — never `Base.metadata.create_all()` outside of tests. After changing a model in `app/models/`:

```bash
alembic revision --autogenerate -m "describe the change"
```

**Always review the generated migration by hand before applying it.** Alembic's autogenerate does not reliably order tables with circular foreign keys (this schema has one: `maintenance_records` and `maintenance_schedules` reference each other) — the initial migration (`alembic/versions/e4ef24ae4574_initial_schema.py`) required manual reordering and a separate `op.create_foreign_key` call for exactly this reason. If autogenerate reports "Cannot correctly sort tables" in its warnings, check the generated file's table creation order manually.

Apply migrations:

```bash
alembic upgrade head
```

## Tests

Tests run against a real, disposable PostgreSQL database — the test suite creates a fresh `wrinklebyte_test_<random>` database (derived from your `DATABASE_URL`'s host/credentials) at the start of the session and drops it afterward, so it never touches your dev database, and all tables are truncated between individual tests for isolation.

```bash
pytest
pytest -v                          # verbose
pytest tests/test_assets.py        # a single file
pytest -k household_isolation       # by keyword
```

17 tests currently cover: registration/login/refresh (both failure and success paths), JWT auth enforcement on protected routes, asset CRUD (including nested vehicle/equipment/property detail tables), optimistic-concurrency version bumping, soft-delete behavior, cross-household tenant isolation, and the recurrence engine's due-date/overdue calculations.

### Troubleshooting

- **`InterfaceError: another operation is in progress`** when running async tests: this is almost always an event-loop mismatch between a session-scoped async fixture (the test DB engine) and per-test event loops. `pyproject.toml` pins `asyncio_default_fixture_loop_scope = "session"` and `asyncio_default_test_loop_scope = "session"` to keep everything on one loop — don't add a custom `event_loop` fixture back into `conftest.py` without understanding why it was removed.
- **`InsecureKeyLengthWarning` from PyJWT**: your `JWT_SECRET` is under 32 bytes. Harmless for local dev with the example secret, but generate a real one (see table above) before deploying anywhere real.

## Project layout

- `app/models/` — SQLAlchemy models. `mixins.py` defines the sync envelope (`id`, `household_id`, `version`, `updated_at`, `deleted_at`, `updated_by_device_id`) shared by every syncable entity — see `../docs/architecture.md`.
- `app/api/v1/` — versioned REST endpoints. `sync.py` (Phase 2) will hold the dedicated sync protocol endpoint.
- `app/core/recurrence.py` — canonical due-date/usage calculation, mirrored in the mobile app's Kotlin shared module (`shared/src/commonMain/kotlin/com/wrinklebyte/domain/RecurrenceEngine.kt` in `tendfida-mobile`).
- `app/storage/` — pluggable attachment storage (`local_disk` default, `s3` optional).
- `alembic/` — schema migrations. Every model change needs a reviewed migration, not `create_all()`.
- `tests/conftest.py` — the per-session disposable test database and per-test table truncation described above.
