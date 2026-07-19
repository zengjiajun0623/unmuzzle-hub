#!/usr/bin/env python3
"""Create or update index/operators.json, signed by the root key.

The root key stays offline; this is the only operation that needs it.
Operators (online keys, possibly held by different people or machines)
sign model entries; clients trust any operator in the root-signed set.

Usage:
  python3 scripts/sign_operators.py --sign-key ~/.minisign/unmuzzle.key \
      [--add name=pubkey ...] [--remove name] [--index-dir index]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unmuzzle import sign as signmod  # noqa: E402
from unmuzzle.trust import canonical_operators_payload  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sign-key", required=True, help="minisign ROOT secret key")
    p.add_argument("--add", action="append", default=[],
                   metavar="name=pubkey", help="add or replace an operator (repeatable)")
    p.add_argument("--remove", action="append", default=[],
                   metavar="name", help="revoke an operator (repeatable)")
    p.add_argument("--index-dir", default="index")
    args = p.parse_args()

    path = Path(args.index_dir) / "operators.json"
    if path.exists():
        doc = json.loads(path.read_text())
    else:
        doc = {"version": 1, "root_pubkey": "", "operators": {}}

    root = signmod.pubkey_from_secret(Path(args.sign_key))
    doc["root_pubkey"] = root

    for kv in args.add:
        name, _, key = kv.partition("=")
        if not name or not key:
            p.error(f"--add needs name=pubkey, got {kv!r}")
        doc["operators"][name] = key
    for name in args.remove:
        doc["operators"].pop(name, None)
    if not doc["operators"]:
        p.error("operator set would be empty; refusing to sign")

    payload = canonical_operators_payload(doc)
    doc["signature"] = signmod.sign(payload, Path(args.sign_key))
    path.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"signed {path}: root={root[:16]}... operators={list(doc['operators'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
