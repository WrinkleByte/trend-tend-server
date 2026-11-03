#!/usr/bin/env bash
# Builds the two production images (backend, web) for a release, tagged
# with the version from backend/pyproject.toml plus "latest".
#
# Usage:
#   scripts/build-release-images.sh            # build for this machine's arch, load locally
#   scripts/build-release-images.sh --push     # build amd64 + arm64 and push to every registry
#
# Every release goes to BOTH Docker Hub (docker.io/wrinklebyte/...) and the
# GitHub Container Registry (ghcr.io/wrinklebyte/...), the same image under
# each name. Docker Hub is the default docker-compose.prod.yml pulls from;
# GHCR sits next to the source for anyone forking it, and has no anonymous
# pull rate limit. Override the list with WRINKLEBYTE_PUBLISH_PREFIXES
# (space-separated) to publish elsewhere, e.g. a fork's own namespace.
#
# --push needs `docker login` to each registry first (for GHCR:
# `docker login ghcr.io` with a token that has write:packages), and a buildx builder
# that can target both architectures: one-time setup on an amd64 box is
#   docker run --privileged --rm tonistiigi/binfmt --install arm64
#   docker buildx create --name wrinklebyte-multiarch --use
# arm64 matters: Raspberry Pis, Apple-silicon Macs and many NAS boxes are
# exactly where people self-host this.
#
# Refuses to build from a dirty tree, so a pushed tag always matches a
# commit.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PUSH=false
if [[ "${1:-}" == "--push" ]]; then
    PUSH=true
elif [[ -n "${1:-}" ]]; then
    echo "Unknown argument: $1" >&2
    exit 2
fi

VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' backend/pyproject.toml | head -1)"
if [[ -z "$VERSION" ]]; then
    echo "Couldn't read version from backend/pyproject.toml" >&2
    exit 1
fi
WEB_VERSION="$(sed -n 's/^  "version": "\(.*\)",$/\1/p' web/package.json | head -1)"
if [[ "$WEB_VERSION" != "$VERSION" ]]; then
    echo "Version mismatch: backend/pyproject.toml=$VERSION web/package.json=$WEB_VERSION" >&2
    exit 1
fi
if ! grep -q "WRINKLEBYTE_VERSION:-$VERSION}" docker-compose.prod.yml; then
    echo "docker-compose.prod.yml's default WRINKLEBYTE_VERSION isn't $VERSION -- update it so" >&2
    echo "a fresh install pulls the release being built." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree has uncommitted changes; commit or stash them first." >&2
    exit 1
fi
COMMIT="$(git rev-parse --short HEAD)"

read -r -a PREFIXES <<< "${WRINKLEBYTE_PUBLISH_PREFIXES:-wrinklebyte ghcr.io/wrinklebyte}"

if $PUSH; then
    PLATFORM_ARGS=(--platform linux/amd64,linux/arm64 --push)
else
    PLATFORM_ARGS=(--load)
fi

for component in backend web; do
    # One build, tagged under every registry, so the copies are
    # byte-identical rather than separate builds that merely share a name.
    tags=()
    for prefix in "${PREFIXES[@]}"; do
        tags+=(--tag "$prefix/wrinklebyte-$component:$VERSION" --tag "$prefix/wrinklebyte-$component:latest")
    done
    echo "==> wrinklebyte-$component:$VERSION ($COMMIT) -> ${PREFIXES[*]}"
    docker buildx build \
        "${PLATFORM_ARGS[@]}" \
        --file "$component/Dockerfile.prod" \
        --build-arg "VERSION=$VERSION" \
        --label "org.opencontainers.image.revision=$COMMIT" \
        "${tags[@]}" \
        "$component"
done

echo
if $PUSH; then
    for prefix in "${PREFIXES[@]}"; do
        echo "Pushed $prefix/wrinklebyte-{backend,web}:{$VERSION,latest} for amd64 + arm64."
    done
    echo "Tag the commit too:  git tag v$VERSION $COMMIT"
else
    echo "Built wrinklebyte-{backend,web}:$VERSION locally under: ${PREFIXES[*]}"
    echo "Smoke-test with:  scripts/smoke-test-prod.sh"
fi
