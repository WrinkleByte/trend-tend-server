# Tendfida — System Architecture

Tendfida tracks maintenance for homes, vehicles, and general equipment (lawn mowers, snow blowers, HVAC systems, and more) — recurring schedules, service history, and costs per asset.

## System overview

Three components, two repositories:

- **Backend** (this repo, `backend/`): Python + FastAPI + PostgreSQL. Open source, self-hostable, free for personal use.
- **Web app** (this repo, `web/`): React + Vite. Serves as the connected web UI for a self-hosted backend, and as an installable, offline-capable PWA. See [`pwa-offline.md`](pwa-offline.md) for the offline design specifically.
- **Mobile apps** (companion `tendfida-mobile` repo): native iOS (SwiftUI) and Android (Jetpack Compose) apps sharing a Kotlin Multiplatform core, sold commercially, fully standalone-capable with optional sync to a self-hosted backend instance.

Sync is optional in every direction: mobile apps work with zero backend, and the backend/web app work with zero mobile clients. Where sync does happen, all three client types (iOS, Android, web PWA) speak the exact same HTTP sync protocol (Section 3) against one backend contract.

## 1. Domain Model

Every syncable table shares a common **sync envelope** mixin so the sync protocol (Section 3) works generically across entity types rather than via bespoke per-table logic:

- `id` (UUID, client-generatable — mobile can create records offline without a server round-trip)
- `household_id` (UUID FK — tenant partition key present on every row)
- `created_at`, `updated_at` (UTC timestamptz, server-stamped on write)
- `updated_by_device_id` (FK → SyncDevice — used for LWW tie-breaking and to exclude sync "echoes" back to the originating device)
- `deleted_at` (nullable — **soft delete only**; hard deletes break sync tombstoning)
- `version` (int, incremented on every write — drives optimistic-concurrency conflict *detection*; `updated_at` drives the *resolution* policy)

### Household (tenant)
`id`, `name`, `owner_user_id`, `settings` (jsonb: default currency, unit system, default conflict-mode suggestion).

### User
`id`, `email` (unique per server), `password_hash` (nullable — a user might auth via API key only), `display_name`.

### HouseholdMembership (join)
`household_id`, `user_id`, `role` (`owner` | `member`), `invited_by_user_id`, `joined_at`. A household can have N memberships; a user can belong to N households (e.g. their own home plus a shared vacation property).

### HouseholdInvite
`id`, `household_id`, `invited_email`, `role`, `token` (single-use, expiring), `status` (`pending`/`accepted`/`revoked`/`expired`), `created_by_user_id`, `expires_at`.

### Asset (polymorphic base + typed side tables)
Base: `id`, `household_id`, `asset_type` (`vehicle` | `equipment` | `property` | `home_system`), `name`, `notes`, `photo_attachment_id`, `status` (`active`/`archived`/`disposed`), `purchase_date`, `purchase_cost`, plus sync mixin.

- `VehicleDetails` (1:1, asset_type=vehicle): `vin`, `make`, `model`, `year`, `license_plate`, `current_mileage`, `mileage_unit`, `fuel_type`.
- `EquipmentDetails` (1:1, asset_type=equipment — mowers, snow blowers, generators): `manufacturer`, `model_number`, `serial_number`, `warranty_expiration`.
- `PropertyDetails` (1:1, asset_type=property or home_system): `address`, `parent_asset_id` (nullable self-FK — e.g. an HVAC unit belongs to a Property), `install_date`.

This keeps the base `assets` table narrow and shared across list/sync/reminder logic, while type-specific fields live in focused side tables joined only when needed. Adding a new asset type later (e.g. `boat`) doesn't require migrating the base table.

### MaintenanceRecord
`id`, `household_id`, `asset_id`, `performed_at`, `performed_by`/`performed_by_user_id` (nullable — could be a third-party shop), `category` (enum + free-text `custom_category`), `description`, `cost`, `currency`, `odometer_reading` (nullable, vehicles), `schedule_id` (nullable — if this record fulfills a scheduled reminder), plus sync mixin. Attachments link via a `RecordAttachment` join table, not a column.

### MaintenanceSchedule (recurring reminder rule)
`id`, `household_id`, `asset_id`, `name` (e.g. "Oil change"), `interval_type` (`time` | `usage` | `both`), `interval_days`, `interval_usage_amount` (e.g. 5000 miles), `usage_field`, `anchor_date`/`anchor_usage_value`, `last_completed_record_id`, `active`, plus sync mixin.

`next_due_date` / `next_due_usage` / `is_overdue` are **computed, not stored** — derived by a recurrence engine implemented identically in Python (`backend/app/core/recurrence.py`) and Kotlin (mobile shared module), validated against a shared test-vector fixture set so both stay behaviorally identical.

### Attachment
`id`, `household_id`, `original_filename`, `content_type`, `size_bytes`, `storage_backend` (`local_disk` | `s3`), `storage_key`, `sha256` (dedup + integrity), `thumbnail_storage_key`, `captured_at`, plus sync mixin. Blob bytes never travel through the row-sync JSON payload — only metadata syncs there; bytes sync via a separate content-addressed transfer (Section 3). Content-addressed + immutable means there is no conflict case for blob bytes, ever.

### SyncDevice
`id`, `household_id`, `user_id`, `platform` (`ios`/`android`/`web`), `device_name`, `last_sync_at`, `last_sync_cursor`, `conflict_resolution_mode` (`last_write_wins` | `manual`), `revoked_at` (remote deauth of a lost device).

### ApiToken
`id`, `household_id`, `user_id`, `name`, `token_hash` (never store raw — shown once at creation), `scopes`, `last_used_at`, `expires_at`, `revoked_at`.

## 2. Backend Architecture (FastAPI + Postgres)

```
backend/
  app/
    main.py, config.py
    db/            # SQLAlchemy async engine, session factory
    models/        # one module per entity + mixins.py (sync envelope)
    schemas/        # Pydantic request/response models
    api/
      deps.py       # get_current_principal (JWT or API key), household scoping, RBAC
      v1/
        auth.py                 # login, refresh, register, invite-accept
        households.py            # CRUD + invites
        assets.py / maintenance_records.py / maintenance_schedules.py
        attachments.py            # upload URL issuance, download, metadata CRUD
        api_tokens.py             # create/list/revoke (web settings page)
        sync.py                   # THE sync endpoint — most architecturally critical file
    core/
      security.py    # JWT + argon2 password hashing + API key generation/verification
      recurrence.py  # canonical next-due-date/usage logic (mirrored in Kotlin)
    storage/
      base.py, local_disk.py, s3.py, factory.py   # StorageBackend abstraction
  alembic/versions/
  tests/
```

**Multi-tenancy** is enforced at the application layer via `household_id` row-scoping on every query, funneled through a shared `household_scoped_query()` helper so isolation is structurally hard to forget rather than a convention any single handler could skip. Postgres RLS is worth adding later as defense-in-depth once the schema stabilizes.

**Auth — both mechanisms as first-class, unified into one dependency.** `get_current_principal` resolves either a JWT bearer token or a prefixed API-key token (e.g. `mnt_live_...`, hashed at rest) into the same `Principal(user_id, household_id, role, device_id)` object — endpoints never know which auth mechanism was used.

- Password login: `POST /auth/login` → short-lived access JWT (~15 min) + refresh token (httpOnly cookie on web, platform Keychain/Keystore on mobile).
- API key pairing: created in web Settings (`POST /api-tokens`), shown once, rendered as a QR code encoding a JSON pairing payload for the "scan into mobile app" flow:

  ```json
  {"v": 1, "server": "https://example.com", "token": "mnt_live_..."}
  ```

  `v` is a schema version (currently `1`); `server` is `window.location.origin` — the same origin the token was issued from; `token` is the raw bearer token, present only in this one response/QR. Mobile clients parse this directly (plain JSON, no base64 or custom URI scheme) into `SyncEngine.validateAndPair(server, token)`'s arguments.

**Sharing/invite flow.** `POST /households/{id}/invites` creates a `HouseholdInvite`; `POST /auth/invite/accept` creates the `HouseholdMembership` row. Roles: `owner` (full control incl. removing members, deleting household) and `member` (full CRUD on assets/records/schedules).

**File storage abstraction.** `StorageBackend` ABC (`put`/`get`/`delete`/`url_for`) with `local_disk` and `s3` implementations (boto3 — works against AWS S3, MinIO, R2, B2 via configurable endpoint). The backend decides local-disk-vs-S3 from its own config and tells clients which upload path to use in the response, so clients don't need per-deployment configuration.

## 3. Sync Protocol

One JSON/HTTP contract shared by iOS, Android, and the web PWA — implemented once, exercised identically by all three.

**Conflict detection.** Every row carries `version` and `updated_at`. A client pushes a change with `base_version = N`; if the server's current version is still `N`, the write succeeds trivially (`WHERE id=:id AND version=:base_version`). If the server's version is `> N`, that's a genuine conflict.

**Pull** — `POST /api/v1/sync/pull`
```json
Request:  { "cursor": "<opaque-string-or-null>", "device_id": "<uuid>" }
Response: {
  "changes": [
    { "entity_type": "asset", "id": "...", "version": 7, "updated_at": "...",
      "deleted": false, "data": { "...": "full row" } }
  ],
  "next_cursor": "<opaque-string>",
  "has_more": true
}
```
The cursor is an opaque, server-generated keyset-pagination token over a per-household change log; clients never interpret it. Excludes the requesting device's own echoes.

**Push** — `POST /api/v1/sync/push`
```json
Request: {
  "device_id": "<uuid>",
  "changes": [
    { "entity_type": "maintenance_record", "id": "...", "base_version": 4,
      "data": { "...": "fields" }, "client_updated_at": "..." }
  ]
}
Response: {
  "results": [
    { "id": "...", "status": "accepted", "new_version": 5, "server_updated_at": "..." },
    { "id": "...", "status": "conflict", "server_version": 6, "server_data": {}, "client_data": {} },
    { "id": "...", "status": "rejected", "reason": "validation_error", "detail": "..." }
  ]
}
```
Processed per-row (not one giant transaction), so one bad row never blocks the rest of the batch.

**Last-write-wins (default).** Resolved **client-side** on receiving a `conflict` result: compare `client_data.updated_at` vs `server_data.updated_at`. Newer wins — either re-push with the corrected `base_version`, or discard the local pending change and accept `server_data`. Invisible to the user, resolved within the same sync cycle.

**Manual conflict resolution.** On `conflict`, the client does *not* auto-resolve. It writes to a local `pending_conflicts` store and surfaces a Conflict Review screen. The local pending edit stays in the outbox, untouched.

- **Approve all**: commits the currently-shown per-item choice (keep mine / keep theirs) for every conflict — reuses the same force-repush / accept-remote mechanics as LWW.
- **Defer/abort**: closes the review screen without touching `pending_conflicts` or the outbox. This is a no-op by construction — "defer" isn't a distinct state, it's the absence of a resolution action, so nothing is ever lost by ignoring it. Unrelated records keep syncing normally every cycle, since conflicts are per-record, not global.

**Attachment blobs sync separately from metadata rows.** Metadata rows go through the normal pull/push protocol; blob bytes sync via `GET/POST /api/v1/attachments/{id}/blob` (or a pre-signed S3 PUT), deduped by `sha256`. Content-addressed + immutable blobs mean there is no conflict case for blob bytes, ever.

The **web PWA** registers as its own `SyncDevice` (`platform=web`) and calls this exact same pull/push contract from its own offline queue (see [`pwa-offline.md`](pwa-offline.md)) — it is not special-cased as "always connected."

## 4. Mobile (KMP) Architecture

Lives in the companion `tendfida-mobile` repo.

```
shared/src/commonMain/kotlin/com/tendfida/
  db/            # SQLDelight schema mirroring backend entities 1:1
  network/        # Ktor client, auth header injection, kotlinx.serialization DTOs
  sync/           # SyncEngine, Outbox, ConflictStore, SyncScheduler (expect/actual per platform)
  domain/         # RecurrenceEngine, CostAggregation, OverdueCalculator (ported 1:1 from core/recurrence.py)
  repository/     # AssetRepository, MaintenanceRecordRepository, ScheduleRepository — the only
                  # API surface native UI consumes; reads/writes SQLDelight directly, never network
  config/         # SyncConfig — is a server paired? URL, credential, conflict mode
iosMain/          # NativeSqliteDriver, BGTaskScheduler
androidMain/      # AndroidSqliteDriver, WorkManager
```

**Standalone-first principle.** Every install syncs to itself first — repositories only ever read/write the local SQLDelight DB, with no code branch for "standalone vs. synced mode." A local `SyncDevice` row is created at first launch regardless of pairing status. Pairing to a server later is a zero-schema-change operation: it just gives the already-running `SyncEngine` a remote to talk to and triggers an initial reconciliation. Ktor is only ever invoked from within `SyncEngine`, so no UI path can accidentally require network.

**Native UI.** SwiftUI consumes shared-module `Flow`s via KMP-NativeCoroutines (Flow → Swift AsyncSequence/Combine); Jetpack Compose consumes the same `Flow`s natively via `collectAsState()`. Both platforms call identical `Repository`/`SyncEngine` APIs — platform code is UI plus `expect/actual` implementations (SQLite driver, background scheduling, Keychain/Keystore credential storage, camera/file-picker for attachment capture).

## 5. Web Frontend + Offline PWA

See [`pwa-offline.md`](pwa-offline.md) for the full offline/PWA design. In short: React + Vite, Dexie.js (IndexedDB) as the offline-first local store, Workbox-based service worker, and the same sync protocol from Section 3.

## 6. Repository Structure

Two repos:

- **`tendfida`** (this repo) — public, source-available under a noncommercial license (see root `LICENSE`). Monorepo containing `backend/` and `web/`, kept together because they share a tight OpenAPI contract and release together via one `docker-compose up` for self-hosters.
- **`tendfida-mobile`** — private, commercial. Contains `shared/` (KMP module), `iosApp/` (SwiftUI), `androidApp/` (Compose), release automation.

Mobile and backend interact **only** over the versioned sync contract in Section 3 — no cross-repo code imports. The OpenAPI schema should be published as a versioned artifact mobile CI can pin against, so a backend change can't silently break a mobile build.

## 7. Phased Build Roadmap

- **Phase 0 — Foundations**: backend skeleton, Postgres, core models (sync columns present from day one), Alembic baseline, password-only JWT auth, basic household-scoped CRUD. Mobile: KMP scaffold, SQLDelight schema, local-only UI shells.
- **Phase 1 — MVP (shippable on its own)**: full local CRUD across the KMP shared module + both native UIs, recurrence/overdue/cost logic surfaced in UI, local attachment capture. This phase alone is a sellable app-store product.
- **Phase 2 — Sync protocol + first mobile client**: full pull/push, outbox/versioning/conflict-detection, LWW resolution, both auth mechanisms, manual conflict UI, attachment blob sync.
- **Phase 3 — Second mobile platform**: primarily UI work, since business/sync logic already lives in the shared module.
- **Phase 4 — Web PWA offline layer**: sequenced after the sync protocol is battle-tested against real mobile clients.
- **Phase 5 — Household sharing/invites**: additive/late, since it isn't needed for a single-tenant-per-household sync model to work.
- **Phase 6 — Ongoing hardening**: S3-compatible storage, Postgres RLS, device/token management UI, backup/export tooling.

## Verification

- **Backend**: pytest against a real (dockerized) Postgres — CRUD, both auth mechanisms, household isolation, sync pull/push round-trips including forced conflicts.
- **Recurrence parity**: a shared JSON test-vector fixture run against both the Python and Kotlin recurrence engines to prove they stay behaviorally identical.
- **Mobile**: KMP shared-module unit tests (`commonTest`); manual smoke tests in the iOS Simulator / Android emulator.
- **Sync end-to-end**: manual two-device tests — offline edits on both, reconnect, verify LWW and manual-mode behavior without data loss.
- **PWA offline**: install to iOS Safari home screen, airplane mode, CRUD, reconnect, verify reconciliation and that storage isn't evicted once actually installed.
