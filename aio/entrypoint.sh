#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# Starts the all-in-one container: PostgreSQL, then migrations, then the API
# and nginx. If any of the three exits, the others are stopped and the
# container exits non-zero, so Docker's restart policy takes over rather
# than leaving a half-working server up.
set -euo pipefail

log() { echo "[trend-tend] $*"; }
die() { echo "[trend-tend] ERROR: $*" >&2; exit 1; }

DATA=/data
SECRETS="$DATA/secrets.env"
ATTACHMENTS="$DATA/attachments"

[[ -w "$DATA" ]] || die "$DATA is not writable by uid $(id -u). If you bind-mount a host directory, chown it to 999:999 first."

# --- Secrets: generated once, kept in the volume, never printed ----------
if [[ ! -f "$SECRETS" ]]; then
    log "first start: generating secrets in $SECRETS"
    gen() { python3 -c 'import secrets; print(secrets.token_urlsafe(48))'; }
    (
        umask 077
        {
            echo "# Generated on first start. Back this file up with the rest of /data:"
            echo "# without it the database password and every login token are lost."
            echo "POSTGRES_PASSWORD=$(gen)"
            echo "APP_DB_PASSWORD=$(gen)"
            echo "JWT_SECRET=$(gen)"
        } > "$SECRETS"
    )
fi
# Values from the file fill in only what the environment didn't set, so
# `-e JWT_SECRET=...` still wins.
while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    [[ -z "${!key:-}" ]] && export "$key=$value"
done < "$SECRETS"

# --- PostgreSQL ------------------------------------------------------------
if [[ -s "$PGDATA/PG_VERSION" ]]; then
    have="$(cat "$PGDATA/PG_VERSION")"
    [[ "$have" == "$PG_MAJOR" ]] || die "the database in $PGDATA was created by PostgreSQL $have, but this image runs PostgreSQL $PG_MAJOR. Nothing has been changed. Go back to the image version you were running, and see the release notes of this version for how to move your data across: https://github.com/wrinklebyte/trend-tend-server/releases"
else
    log "first start: creating the database"
    pwfile="$(mktemp)"
    printf '%s\n' "$POSTGRES_PASSWORD" > "$pwfile"
    initdb -D "$PGDATA" -U wrinklebyte --pwfile="$pwfile" \
        --auth-local=peer --auth-host=scram-sha-256 --encoding=UTF8 >/dev/null
    rm -f "$pwfile"
fi

# Only ever reachable from inside this container.
postgres -D "$PGDATA" -c listen_addresses=127.0.0.1 -c unix_socket_directories=/var/run/postgresql &
pg_pid=$!

for _ in $(seq 1 60); do
    pg_isready -q -h 127.0.0.1 -U wrinklebyte && break
    kill -0 "$pg_pid" 2>/dev/null || die "PostgreSQL exited during startup (see the log above)"
    sleep 1
done
pg_isready -q -h 127.0.0.1 -U wrinklebyte || die "PostgreSQL did not become ready within 60s"

pg() { PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U wrinklebyte -d postgres -v ON_ERROR_STOP=1 "$@"; }
if [[ "$(pg -Atc "SELECT 1 FROM pg_database WHERE datname = 'wrinklebyte'")" != "1" ]]; then
    pg -qc "CREATE DATABASE wrinklebyte OWNER wrinklebyte"
fi

# --- API configuration -----------------------------------------------------
if [[ -z "${FRONTEND_URL:-}" ]]; then
    export FRONTEND_URL="http://localhost:8080"
    log "WARNING: FRONTEND_URL is not set; using $FRONTEND_URL. Links in password-reset and invite emails, and the mobile pairing code, will point there. Set -e FRONTEND_URL=<the address people use to reach this server>."
fi
export PUBLIC_API_URL="${PUBLIC_API_URL:-$FRONTEND_URL}"
export DATABASE_URL="postgresql+asyncpg://wrinklebyte:${POSTGRES_PASSWORD}@127.0.0.1:5432/wrinklebyte"
export RUNTIME_DATABASE_URL="postgresql+asyncpg://wrinklebyte_app:${APP_DB_PASSWORD}@127.0.0.1:5432/wrinklebyte"
export STORAGE_BACKEND=local_disk
export STORAGE_LOCAL_ROOT="$ATTACHMENTS"
mkdir -p "$ATTACHMENTS"

log "applying database migrations"
(cd /app && alembic upgrade head)

# --- Run -----------------------------------------------------------------
# One uvicorn worker on purpose: the login rate limiter is in-process memory
# (see backend/Dockerfile.prod).
(cd /app && exec uvicorn app.main:app --host 127.0.0.1 --port 8000) &
api_pid=$!
nginx -g 'daemon off;' &
nginx_pid=$!

shutdown() {
    log "stopping"
    kill -TERM "$nginx_pid" "$api_pid" 2>/dev/null || true
    wait "$nginx_pid" "$api_pid" 2>/dev/null || true
    # SIGINT = Postgres "fast" shutdown: clean, and quick enough for
    # `docker stop`'s default 10s grace period.
    kill -INT "$pg_pid" 2>/dev/null || true
    wait "$pg_pid" 2>/dev/null || true
}
trap 'shutdown; exit 0' TERM INT

log "ready on port 8080 (public URL: $FRONTEND_URL)"
set +e
wait -n "$pg_pid" "$api_pid" "$nginx_pid"
status=$?
set -e
log "a server process exited unexpectedly (status $status)"
shutdown
exit 1
