#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

# Smoke test for the all-in-one image (aio/Dockerfile), run the way a new
# self-hoster would meet it: one `docker run` on an empty volume. Checks
# the same first-run flow as smoke-test-prod.sh, plus what is specific to
# a single container holding its own database:
#   - secrets are generated on first start and are not world-readable
#   - data and the generated secrets survive a container restart
#   - `docker stop` shuts Postgres down cleanly, well inside the grace period
# Removes its container and volume afterwards, pass or fail.
#
# Usage:
#   scripts/smoke-test-aio.sh                  # build from this tree first
#   scripts/smoke-test-aio.sh <image:tag>      # test an already built/pulled image
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

NAME="trend-tend-aio-smoketest"
VOLUME="$NAME-data"
PORT="${SMOKE_PORT:-18081}"
BASE="http://127.0.0.1:$PORT"
IMAGE="${1:-}"

if [[ -z "$IMAGE" ]]; then
    IMAGE="trend-tend-server:smoketest"
    echo "==> building $IMAGE"
    docker build -q -f aio/Dockerfile -t "$IMAGE" . >/dev/null
fi

cleanup() {
    status=$?
    if [[ $status -ne 0 ]]; then
        echo "--- container logs (last 60 lines) ---"
        docker logs --tail 60 "$NAME" 2>&1 || true
    fi
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker volume rm -f "$VOLUME" >/dev/null 2>&1 || true
    exit $status
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

wait_healthy() {
    for _ in $(seq 1 90); do
        [[ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME" 2>/dev/null)" == "healthy" ]] && return 0
        [[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" == "true" ]] || fail "container stopped during startup"
        sleep 2
    done
    fail "container not healthy after 180s"
}

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker volume rm -f "$VOLUME" >/dev/null 2>&1 || true

echo "==> starting $IMAGE on port $PORT (empty volume)"
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8080" \
    -e FRONTEND_URL="$BASE" -v "$VOLUME:/data" \
    --health-interval 2s "$IMAGE" >/dev/null
wait_healthy

echo "==> web app"
curl -fsS "$BASE/" | grep -qi "<html" || fail "web root did not return HTML"

echo "==> API through nginx"
health="$(curl -fsS "$BASE/api/v1/auth/setup-status")" || fail "setup-status unreachable"
echo "    setup-status: $health"
echo "$health" | grep -q '"setup_complete":false' || fail "fresh instance should report setup incomplete"
version="$(docker exec "$NAME" python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())")"
echo "    /health: $version"

echo "==> first account (becomes instance admin)"
creds='{"email":"keep-test-smoke@example.com","password":"Smoke-test-password-123"}'
token="$(curl -fsS -X POST "$BASE/api/v1/auth/register" -H 'Content-Type: application/json' \
    -d '{"email":"keep-test-smoke@example.com","password":"Smoke-test-password-123","display_name":"Smoke","household_name":"keep-test-smoke"}' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")" || fail "registration failed"

echo "==> authenticated API call"
curl -fsS "$BASE/api/v1/assets" -H "Authorization: Bearer $token" >/dev/null || fail "GET /api/v1/assets failed"

echo "==> security headers"
curl -fsSI "$BASE/" | grep -qi "content-security-policy" || fail "missing Content-Security-Policy on /"

echo "==> generated secrets are private"
mode="$(docker exec "$NAME" stat -c '%a' /data/secrets.env)"
[[ "$mode" == "600" ]] || fail "/data/secrets.env has mode $mode, expected 600"

echo "==> clean shutdown"
start=$(date +%s)
docker stop "$NAME" >/dev/null
took=$(( $(date +%s) - start ))
[[ "$(docker inspect -f '{{.State.ExitCode}}' "$NAME")" == "0" ]] || fail "container exited non-zero on docker stop"
(( took < 10 )) || fail "docker stop took ${took}s (hit the kill timeout?)"
docker logs "$NAME" 2>&1 | grep -q "database system is shut down" || fail "Postgres did not report a clean shutdown"
echo "    stopped cleanly in ${took}s"

echo "==> restart keeps data, secrets and logins"
docker start "$NAME" >/dev/null
wait_healthy
curl -fsS "$BASE/api/v1/auth/setup-status" | grep -q '"setup_complete":true' || fail "instance forgot its setup after restart"
curl -fsS -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' -d "$creds" >/dev/null \
    || fail "could not log in after restart"
curl -fsS "$BASE/api/v1/assets" -H "Authorization: Bearer $token" >/dev/null \
    || fail "a token issued before the restart was rejected (JWT secret not persisted?)"

echo
echo "PASS: all-in-one image served a full first-run flow and survived a restart."
