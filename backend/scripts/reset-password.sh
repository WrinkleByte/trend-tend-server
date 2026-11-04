#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# Manual password reset, run *inside* the backend container.
#
# From the host (docker compose project directory), for an interactive
# password prompt:
#   docker compose exec backend scripts/reset-password.sh user@example.com
#
# Or list existing accounts first:
#   docker compose exec backend scripts/reset-password.sh --list
#
# -T is required if you ever pipe/script this non-interactively, but then
# you must pass --password explicitly since there's no tty for the prompt.
set -eu
cd "$(dirname "$0")/.."
exec python -m scripts.reset_password "$@"
