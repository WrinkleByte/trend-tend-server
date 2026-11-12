<!-- SPDX-FileCopyrightText: 2026 WrinkleByte LLC -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Developing Trend & Tend Server

Full system design, including the sync protocol: [`architecture.md`](architecture.md).
PWA offline design: [`pwa-offline.md`](pwa-offline.md).

## Layout

- `backend/` — Python + FastAPI + PostgreSQL (async SQLAlchemy). `app/models/`,
  `app/schemas/`, `app/api/v1/`, `app/core/` (recurrence engine, security),
  `app/storage/` (local disk / S3 abstraction), `alembic/versions/` (migrations).
- `web/` — React + Vite. Dexie.js (IndexedDB) offline store, Workbox service
  worker, and the same sync protocol as the mobile apps.

## Build and test

- Full stack: `docker compose up` from the repo root.
- Backend: `cd backend && .venv/bin/pytest` (needs the Postgres from
  `docker-compose.yml`). Lint: `.venv/bin/ruff check .`.
- Web: `cd web && npm run build`, `npm run lint` (oxlint), `npx tsc --noEmit`.
- Production image (`aio/Dockerfile`, published as `trend-tend-server`):
  `scripts/smoke-test-aio.sh` builds it and tests it on its own (built-in
  database); `scripts/smoke-test-prod.sh --build` tests it in the Compose
  stack next to the official postgres image.
- `scripts/setup-git-hooks.sh` installs pre-commit hooks that run the linters.

## Architectural invariants

Don't break these without a deliberate decision.

- **Household-scoped queries**: every table has `household_id`; all queries go through `household_scoped_query()` (`app/api/deps.py`) so tenant isolation is structural, not convention. This covers an endpoint's own primary resource, but **not automatically a client-supplied foreign key referencing a different table** (e.g. a fuel log's `asset_id`, a maintenance record's `schedule_id`) — those need an explicit `verify_owned_reference()` call (same file) on create/update, or a client can point a row they're allowed to write at another household's row. Found and fixed as a real cross-tenant write vulnerability (Vikunja #32) in every "mirror `fuel_log`" create endpoint and in `sync.py`'s generic push handler (`_apply_change`) — check both code paths (REST create endpoints, and `_REFERENCE_FIELDS` in `sync.py`) when adding a new entity with a cross-table reference. Backstopped at the database layer too (Vikunja #44) — Postgres RLS policies on every `household_scoped_query()`-covered table, keyed off a per-request session GUC (`app/db/rls.py`) — see `docs/architecture.md`'s Multi-tenancy section for how the GUC gets set and how `admin.py`'s legitimate cross-household queries opt out. Enforcement runs through a **second DB role**, `wrinklebyte_app` (created by the `95d3e5f4643e` migration, opt-in via `APP_DB_PASSWORD`/`RUNTIME_DATABASE_URL`) — the app's normal DB role, `wrinklebyte`/docker-compose's `POSTGRES_USER`, is the Postgres cluster's bootstrap role and can never have `SUPERUSER` stripped, so it stays on for migrations only. If you add a table to `_HOUSEHOLD_SCOPED_TABLES`-equivalent scope, it needs its own RLS policy migration **and** must already be covered by `wrinklebyte_app`'s default-privilege grant (it is, automatically, as long as `wrinklebyte` created it) — see `docs/architecture.md` for the full story before touching this again.
- **Sync pull payloads are an explicit allowlist, not every column**: `sync.py`'s `_serialize_row` builds each entity's wire `data` from that entity's own `*SyncData` Pydantic schema (the same one push validates against), not a dynamic walk of `obj.__table__.columns`. A new column added to a model for an unrelated reason doesn't automatically become visible to every client (including old, not-yet-upgraded ones) — it has to be deliberately added to that entity's `*SyncData` schema first. Keep this in mind when adding a column to a `SyncedEntityMixin` table for internal/non-sync bookkeeping (e.g. `maintenance_record.performed_by_user_id`-style fields) — it stays server-only by default now, not leaked by omission.
- **Sync envelope on every syncable table**: `id` (client-generatable UUID), `household_id`, `created_at`/`updated_at`, `updated_by_device_id`, `deleted_at`, `version` — via the shared `SyncedEntityMixin` (`app/models/mixins.py`). Adding a new syncable entity means adding this mixin, not inventing new columns for it.
- **Soft delete only** — never a real `DELETE` on a syncable row. `deleted_at` is the tombstone; hard deletes break sync tombstoning for other devices.
- **New entity type = mirror `fuel_log`**: `app/models/fuel_log.py` / `app/schemas/fuel_log.py` / `app/api/v1/fuel_logs.py` / its Alembic migration / its `sync.py` registry entry is the canonical template other entities (e.g. `trip_log`) should copy structurally.
- **Auth**: `get_current_principal` (`app/api/deps.py`) unifies JWT and API-key auth into one `Principal` — endpoints shouldn't care which was used.
- **Attachments**: metadata rows sync through the normal protocol; blob bytes never travel in the sync JSON payload — separate content-addressed transfer, deduped by `sha256`.
