#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# Reset a user's password from inside a running server container, for an
# admin locked out before email (SMTP) is set up:
#
#   docker exec -it trend-tend trend-tend-reset-password --list
#   docker exec -it trend-tend trend-tend-reset-password user@example.com
#
# With Compose: docker compose -f docker-compose.prod.yml exec server
#   trend-tend-reset-password ...
#
# `docker exec` doesn't see the settings the entrypoint works out at start,
# so this loads them the same way: environment first, then
# /data/secrets.env, then the built-in database's address.
set -euo pipefail

[[ "$(id -u)" == 0 ]] && exec gosu postgres "$0" "$@"

while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    [[ -z "${!key:-}" ]] && export "$key=$value"
done < /data/secrets.env

if [[ -z "${DATABASE_URL:-}" ]]; then
    export DATABASE_URL="postgresql+asyncpg://wrinklebyte:${POSTGRES_PASSWORD}@127.0.0.1:5432/wrinklebyte"
fi

cd /app
exec python3 -m scripts.reset_password "$@"
