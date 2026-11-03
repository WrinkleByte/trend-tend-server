#!/usr/bin/env bash
# Builds the two production images (backend, web) for a release, tagged
# with the version from backend/pyproject.toml plus "latest".
#
# Usage:
#   scripts/build-release-images.sh            # build for this machine's arch, load locally
#   scripts/build-release-images.sh --push     # build amd64 + arm64 and push to the registry
#
# The image names come from WRINKLEBYTE_IMAGE_PREFIX (default "wrinklebyte",
# i.e. docker.io/wrinklebyte/...), the same variable docker-compose.prod.yml
# reads, so what this pushes is exactly what `compose pull` fetches.
#
# --push needs `docker login` to that registry first, and a buildx builder
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

PREFIX="${WRINKLEBYTE_IMAGE_PREFIX:-wrinklebyte}"

if $PUSH; then
    PLATFORM_ARGS=(--platform linux/amd64,linux/arm64 --push)
else
    PLATFORM_ARGS=(--load)
fi

for component in backend web; do
    image="$PREFIX/wrinklebyte-$component"
    echo "==> $image:$VERSION ($COMMIT)"
    docker buildx build \
        "${PLATFORM_ARGS[@]}" \
        --file "$component/Dockerfile.prod" \
        --build-arg "VERSION=$VERSION" \
        --label "org.opencontainers.image.revision=$COMMIT" \
        --tag "$image:$VERSION" \
        --tag "$image:latest" \
        "$component"
done

echo
if $PUSH; then
    echo "Pushed $PREFIX/wrinklebyte-{backend,web}:{$VERSION,latest} for amd64 + arm64."
    echo "Tag the commit too:  git tag v$VERSION $COMMIT"
else
    echo "Built $PREFIX/wrinklebyte-{backend,web}:$VERSION locally. Smoke-test with:"
    echo "  scripts/smoke-test-prod.sh"
fi
