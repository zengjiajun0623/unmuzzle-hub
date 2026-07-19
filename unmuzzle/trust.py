"""Key continuity (trust on first use) for publisher keys.

The index pins every file's sha256 and minisign signs the manifest, but the
publisher's pubkey itself travels in the index. If an index host is ever
compromised or coerced, both the entry and the key can be swapped together
and naive verification still passes.

Defense: remember each publisher's key the first time you see it, and fail
loudly if it ever changes. Same model as SSH host keys. The store is a
plain JSON file at ~/.unmuzzle/known_publishers.json (override with
UNMUZZLE_TRUST_STORE).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_STORE = Path.home() / ".unmuzzle" / "known_publishers.json"


class KeyChangedError(Exception):
    pass


def store_path() -> Path:
    return Path(os.environ.get("UNMUZZLE_TRUST_STORE", str(DEFAULT_STORE)))


def publisher_id(entry_name: str) -> str:
    """Publisher identity is the org: 'org/name' -> 'org'."""
    return entry_name.split("/", 1)[0]


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def check_continuity(entry_name: str, pubkey: str, accept_new: bool = False) -> dict:
    """Pin the publisher's key on first sight; raise KeyChangedError if it
    changes. Returns a status dict for reporting."""
    path = store_path()
    known = _load(path)
    pub = publisher_id(entry_name)
    old = known.get(pub)

    if old == pubkey:
        return {"publisher": pub, "continuity": "ok", "pinned": False}
    if old is None:
        known[pub] = pubkey
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(known, indent=2) + "\n")
        return {"publisher": pub, "continuity": "pinned_first_use", "pinned": True}

    if not accept_new:
        raise KeyChangedError(
            f"PUBLISHER KEY CHANGED for {pub}!\n"
            f"  was: {old}\n"
            f"  now: {pubkey}\n"
            "This can mean a new publisher took over the org, or the index "
            "host was compromised. If you expected the rotation, re-run with "
            "--accept-new-key to pin the new key."
        )
    known[pub] = pubkey
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(known, indent=2) + "\n")
    return {"publisher": pub, "continuity": "accepted_new_key", "pinned": True,
            "previous_key": old}
