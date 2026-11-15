<!--
SPDX-FileCopyrightText: 2026 WrinkleByte LLC
SPDX-License-Identifier: AGPL-3.0-only
-->

# Releasing Trend & Tend Server

How a release goes from `main` to published images. For building and testing,
see [`docs/development.md`](docs/development.md) and the README's "CI" and
"Testing" sections; for running it, the README's "Self-hosting" section.

## Checklist

1. **Everything for the release is merged to `main`**, and CI on `main` is
   green (`.github/workflows/ci.yml`: ruff, migrations, pytest, web lint and
   build, gitleaks, REUSE, and both smoke tests).

2. **Bump the version** on a branch, in these five places, to the same
   `X.Y.Z`:
   - `backend/pyproject.toml` (`version = "X.Y.Z"`)
   - `web/package.json` (`"version": "X.Y.Z"`, line 4; leave
     `web/package-lock.json` alone)
   - `docker-compose.prod.yml` (the `${WRINKLEBYTE_VERSION:-X.Y.Z}` default)
   - `.env.prod.example` (`# WRINKLEBYTE_VERSION=X.Y.Z`)
   - `README.md` (the "Pin a version tag (for example `:X.Y.Z`)" line)

   Commit as `Version X.Y.Z`, open a pull request, merge it once CI passes.

3. **Wait for CI on the merge commit** on `main` to pass.

4. **Tag it** with an annotated tag on that commit, and push the tag:
   ```bash
   git tag -a vX.Y.Z -m "Trend & Tend Server X.Y.Z" <merge-commit>
   git push origin vX.Y.Z
   ```
   The `pre-push` hook runs the full backend suite first (it needs a
   PostgreSQL it can reach through `DATABASE_URL`, or the running compose
   stack).

5. **The release workflow publishes the images** (`.github/workflows/release.yml`,
   triggered only by `v*.*.*` tags). It:
   - checks the tag matches the version in the tree, and stops if it doesn't;
   - builds `trend-tend-server` natively for linux/amd64 and linux/arm64;
   - pushes `X.Y.Z` and `latest` to Docker Hub (`wrinklebyte/trend-tend-server`)
     and GHCR (`ghcr.io/wrinklebyte/trend-tend-server`), with SBOM and
     provenance attestations.

   Other tag names never publish anything, so throwaway tags are safe.

6. **Write the GitHub release** for the tag. Follow the previous releases'
   shape: one-line summary; Upgrading (single container and Compose, and
   whether migrations run); What's new; Image; Help; License.

7. **Upgrade your own instances** the way the release notes tell users to:
   back up, set `WRINKLEBYTE_VERSION=X.Y.Z` (Compose) or pull the new tag
   (single container), `pull`, `up -d`, then check `/health` reports the new
   version.

## Notes

- Alembic migrations run automatically when the server starts. A migration's
  `down_revision` must follow the newest migration on `main`; rebase feature
  branches before release so two heads can't reach a tag.
- Never retag a published version. Fix forward with `X.Y.Z+1`.
