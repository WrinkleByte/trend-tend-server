#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only
"""Read the fields the mobile client actually sends and write them as a manifest.

The backend repo cannot see the mobile repo in CI, so the cross-repo sync
contract is checked in two places:

* here, on a machine that has both checkouts -- regenerate the manifest from
  the Kotlin payloads and diff it against the committed one. A client that
  starts sending a field nobody agreed about shows up as a diff, before a
  build ships carrying it.
* tests/test_sync_contract.py, in CI -- reads the committed manifest and
  asserts the backend declares each field and has a real column for it.

Usage:
    python scripts/sync_contract.py --mobile ../tendfida-mobile --write
    python scripts/sync_contract.py --mobile ../tendfida-mobile --check

Exit codes: 0 clean, 1 drift or unreadable source.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PAYLOAD_FILE = Path("shared/src/commonMain/kotlin/com/wrinklebyte/network/SyncDto.kt")
CLASS_RE = re.compile(r"^data class (\w+SyncPayload)\(")
# @SerialName("wire_name") val kotlinName: Type = default   /   val kotlinName: Type
FIELD_RE = re.compile(r"@SerialName\(\"([^\"]+)\"\)\s*(?:@\w+(?:\([^)]*\))?\s*)*val (\w+)")
PLAIN_RE = re.compile(r"^\s*val (\w+)\s*:")
SKIP_LINE_MARKERS = ("//", "/*", "*")


def _strip_comments(text: str) -> str:
    out, in_block = [], False
    for line in text.splitlines():
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            if "*/" not in s:
                in_block = True
            continue
        if s.startswith(SKIP_LINE_MARKERS):
            continue
        out.append(line)
    return "\n".join(out)


def _class_bodies(text: str) -> dict[str, list[str]]:
    """Wire field names per *SyncPayload class, in declaration order."""
    lines = text.splitlines()
    payloads: dict[str, list[str]] = {}
    for i, line in enumerate(lines):
        m = CLASS_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        fields: list[str] = []
        depth = line.count("(") - line.count(")")
        for j in range(i + 1, len(lines)):
            body = lines[j]
            depth += body.count("(") - body.count(")")
            if depth <= 0:
                break
            sm = FIELD_RE.search(body)
            if sm:
                fields.append(sm.group(1))
                continue
            pm = PLAIN_RE.match(body)
            if pm:
                fields.append(pm.group(1))
        payloads[name] = fields
    return payloads


def _source_commit(mobile: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(mobile), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout.strip()
    except Exception as exc:  # not a checkout, or git unavailable
        print(f"  note: could not read mobile git HEAD: {exc}", file=sys.stderr)
        return "unknown"


def build_manifest(mobile: Path) -> dict:
    path = mobile / PAYLOAD_FILE
    if not path.is_file():
        raise SystemExit(f"no SyncDto.kt under {mobile} -- is --mobile pointing at the mobile checkout?")
    payloads = _class_bodies(_strip_comments(path.read_text(encoding="utf-8", errors="replace")))
    if not payloads:
        raise SystemExit(f"{path} parsed but yielded no *SyncPayload classes")
    return {
        "_comment": (
            "Fields the mobile client puts on the wire, read out of its own payload "
            "classes. Regenerate with scripts/sync_contract.py; tests/test_sync_contract.py "
            "checks this against what the server declares and can store."
        ),
        "source_repo": "tendfida-mobile",
        "source_file": str(PAYLOAD_FILE),
        "source_commit": _source_commit(mobile),
        "payloads": payloads,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mobile", required=True, help="path to the tendfida-mobile checkout")
    ap.add_argument("--manifest", default=str(Path(__file__).resolve().parent.parent / "tests/contract/mobile_sync_payload.json"))
    ap.add_argument("--write", action="store_true", help="write the manifest")
    ap.add_argument("--check", action="store_true", help="fail if the committed manifest differs")
    args = ap.parse_args()

    if not (args.write or args.check):
        ap.error("pick --write or --check")

    manifest = build_manifest(Path(args.mobile))
    path = Path(args.manifest)
    payloads = manifest["payloads"]
    total = sum(len(v) for v in payloads.values())
    print(f"mobile payloads: {len(payloads)} classes, {total} fields, commit {manifest['source_commit'][:9]}")
    for name, fields in sorted(payloads.items()):
        print(f"  {name} ({len(fields)})")

    drift: list[str] = []
    committed: dict = {"payloads": {}}
    if not path.is_file():
        print(f"no committed manifest at {path}")
        if not args.write:
            print("DRIFT (1):")
            for d in drift:
                print(f"  - {d}")
            return 1
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"committed manifest at {path} is unreadable or not valid JSON: {exc}")
            return 1
        if "payloads" not in committed:
            print(f"committed manifest at {path} has no 'payloads' key -- regenerate it with --write")
            return 1

    for name in sorted(set(committed["payloads"]) | set(payloads)):
        old = set(committed["payloads"].get(name, []))
        new = set(payloads.get(name, []))
        if not old:
            drift.append(f"{name}: new payload class ({len(new)} fields)")
        elif not new:
            drift.append(f"{name}: payload class gone from the client")
        else:
            for f in sorted(new - old):
                drift.append(f"{name}.{f}: client sends it, manifest does not know about it")
            for f in sorted(old - new):
                drift.append(f"{name}.{f}: manifest lists it, client no longer sends it")

    if not drift:
        print("manifest matches the client. no drift.")
    else:
        print(f"DRIFT ({len(drift)}):")
        for d in drift:
            print(f"  - {d}")

    if args.write:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"could not write {path}: {exc}")
            return 1
        print(f"wrote {path}")
        return 0
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
