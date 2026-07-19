#!/usr/bin/env python3
"""Validate a publish PR for auto-merge.

Checks, in order. Every failure is reported; no content judgment, only
integrity and namespace rules:

1. The PR touches only index/models/*.json (anything else = manual review).
2. Each entry parses, passes schema validation, and its filename matches
   the model name.
3. The minisign signature verifies against the entry's own publisher key.
4. Key continuity: an established org (in index/publishers.json) must keep
   its registered key. New orgs are allowed only when the org name equals
   the PR author's GitHub username (namespace hygiene).
5. Every HTTP mirror answers a range probe with the manifest's byte size,
   over https only. A torrent URL, if present, must answer 200.

Usage:
  python3 scripts/validate_pr.py --pr-author <github-username> \\
      --head-ref <ref-or-sha> [--files f1.json f2.json]

Prints a verdict line per check and exits nonzero on any failure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unmuzzle import api  # noqa: E402
from unmuzzle.download import USER_AGENT  # noqa: E402
from unmuzzle.index import IndexError, validate_entry  # noqa: E402
from scripts.verify_release import probe_http_file  # noqa: E402

MAX_ENTRY_BYTES = 64 * 1024
FAILURES = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"[FAIL] {msg}")


def ok(msg: str) -> None:
    print(f"[pass] {msg}")


def pr_file(ref: str, path: str) -> str:
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot read {path} from {ref}: {r.stderr.strip()}")
    return r.stdout


def probe(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pr-author", required=True)
    p.add_argument("--head-ref", required=True)
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--publishers", default="index/publishers.json")
    args = p.parse_args()

    # 1. scope: only index/models/*.json
    for f in args.files:
        if not (f.startswith("index/models/") and f.endswith(".json")):
            fail(f"{f}: publish PRs may only touch index/models/*.json (manual review)")
            return 1
    if not args.files:
        fail("no index entries changed")
        return 1
    ok(f"scope: {len(args.files)} entry file(s)")

    publishers = json.loads(Path(args.publishers).read_text()) if Path(args.publishers).exists() else {}

    for f in args.files:
        try:
            raw = pr_file(args.head_ref, f)
        except RuntimeError as e:
            fail(str(e))
            continue
        if len(raw.encode()) > MAX_ENTRY_BYTES:
            fail(f"{f}: entry too large ({len(raw.encode())} bytes)")
            continue
        try:
            data = json.loads(raw)
            entry = validate_entry(data)
        except (json.JSONDecodeError, IndexError) as e:
            fail(f"{f}: {e}")
            continue
        ok(f"{f}: schema valid ({entry.name})")

        slug = entry.name.replace("/", "__")
        if f != f"index/models/{slug}.json":
            fail(f"{f}: filename must be index/models/{slug}.json")
            continue

        # 3. signature self-consistency
        try:
            sig = api.check_signature(entry, require=True)
            ok(f"{entry.name}: signature verifies")
        except api.UnmuzzleError as e:
            fail(f"{entry.name}: {e}")
            continue

        # 4. key continuity / namespace
        org = entry.name.split("/", 1)[0]
        registered = publishers.get(org)
        if registered:
            if registered != entry.publisher_pubkey:
                fail(f"{entry.name}: key for org '{org}' does not match index/publishers.json")
                continue
            ok(f"{entry.name}: org key matches registry")
        elif org.lower() != args.pr_author.lower():
            fail(f"{entry.name}: new org '{org}' must equal the PR author's username "
                 f"('{args.pr_author}'); established orgs are listed in index/publishers.json")
            continue
        else:
            ok(f"{entry.name}: new publisher org '{org}' (will be registered on merge)")

        if not entry.license:
            fail(f"{entry.name}: license field is required")
            continue

        # 5. mirrors live (https only)
        for base in entry.http:
            if not base.startswith("https://"):
                fail(f"{entry.name}: mirror must be https: {base}")
                continue
            for file_ in entry.files:
                try:
                    probe_http_file(base, file_["path"], file_["size"])
                    ok(f"{entry.name}: mirror serves {file_['path']} ({base})")
                except Exception as e:
                    fail(f"{entry.name}: mirror probe failed for {file_['path']} on {base}: {e}")
        if entry.torrent and not probe(entry.torrent):
            fail(f"{entry.name}: torrent URL not reachable: {entry.torrent}")

    if FAILURES:
        print(f"\n{len(FAILURES)} problem(s) found")
        return 1
    print("\nvalidation green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
