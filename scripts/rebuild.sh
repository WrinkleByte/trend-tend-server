#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# Stops the docker-compose stack, rebuilds images (picks up code changes
# and any edits to the root .env — see docker-compose.yml/.env.example),
# and starts it back up in the background.
#
# `down` (not `stop`) so containers are recreated from the fresh images
# rather than just restarted from the old ones; named volumes
# (postgres_data, attachments_data) aren't touched either way.
#
# Usage: scripts/rebuild.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

docker compose down
sleep 30
docker compose build
docker compose up -d
docker compose ps
