#!/usr/bin/env bash
# One-time (per clone) setup: installs this repo's tracked hooks
# (.githooks/) into .git/hooks/, where git actually looks for them.
# .git/hooks/ itself isn't version-controlled, so the hooks need to live
# somewhere tracked (.githooks/) and get copied in — this script is that
# copy step. Safe to re-run any time (e.g. after a hook script changes).
#
# Deliberately copies files rather than setting `git config core.hooksPath
# .githooks` — same end result, but it doesn't touch repo-wide git config.
#
# Usage: scripts/setup-git-hooks.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SOURCE_DIR="$REPO_ROOT/.githooks"
TARGET_DIR="$REPO_ROOT/.git/hooks"

for hook in "$SOURCE_DIR"/*; do
    name="$(basename "$hook")"
    cp "$hook" "$TARGET_DIR/$name"
    chmod +x "$TARGET_DIR/$name"
    echo "Installed $name -> .git/hooks/$name"
done

echo "Done. See README.md's \"Local CI (git hooks)\" section for what these check."
