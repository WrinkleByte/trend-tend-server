#!/usr/bin/env bash
# Brings up docker-compose.prod.yml from nothing -- fresh volumes, freshly
# generated secrets -- and checks it the way a new self-hoster would meet
# it: the web app loads, /api/ reaches the backend through nginx, the first
# account can register, and an authenticated sync call succeeds. Tears
# everything down (including its volumes) afterwards, pass or fail.
#
# Usage:
#   scripts/smoke-test-prod.sh            # use the images as already built/pulled
#   scripts/smoke-test-prod.sh --build    # build from this source tree first
#
# Runs as its own Compose project on its own port, so it never touches a
# real instance's containers or volumes.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PROJECT="wrinklebyte-smoketest"
PORT="${SMOKE_PORT:-18080}"
BASE="http://127.0.0.1:$PORT"
ENV_FILE="$(mktemp)"
BUILD_ARGS=()
[[ "${1:-}" == "--build" ]] && BUILD_ARGS=(--build)

secret() { python3 -c "import secrets; print(secrets.token_urlsafe(48))"; }
cat > "$ENV_FILE" <<ENV
POSTGRES_PASSWORD=$(secret)
APP_DB_PASSWORD=$(secret)
JWT_SECRET=$(secret)
FRONTEND_URL=$BASE
WEB_HOST_PORT=$PORT
ENV

compose() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.prod.yml "$@"; }

cleanup() {
    status=$?
    if [[ $status -ne 0 ]]; then
        echo "--- backend logs (last 40 lines) ---"
        compose logs --tail 40 backend || true
    fi
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -f "$ENV_FILE"
    exit $status
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "==> starting $PROJECT on port $PORT"
compose up -d "${BUILD_ARGS[@]}" --wait --wait-timeout 180

echo "==> web app"
curl -fsS "$BASE/" | grep -qi "<html" || fail "web root did not return HTML"

echo "==> health through nginx"
health="$(curl -fsS "$BASE/api/v1/auth/setup-status")" || fail "setup-status unreachable"
echo "    setup-status: $health"
echo "$health" | grep -q '"setup_complete":false' || fail "fresh instance should report setup incomplete"

version="$(compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())")"
echo "    backend /health: $version"

echo "==> first account (becomes instance admin)"
token="$(curl -fsS -X POST "$BASE/api/v1/auth/register" \
    -H 'Content-Type: application/json' \
    -d '{"email":"keep-test-smoke@example.com","password":"Smoke-test-password-123","display_name":"Smoke","household_name":"keep-test-smoke"}' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")" || fail "registration failed"

echo "==> authenticated API call"
curl -fsS "$BASE/api/v1/assets" -H "Authorization: Bearer $token" >/dev/null || fail "GET /api/v1/assets failed"

echo "==> security headers"
curl -fsSI "$BASE/" | grep -qi "content-security-policy" || fail "missing Content-Security-Policy on /"

echo
echo "PASS: production stack came up clean and served a full first-run flow."
