"""Key continuity (trust on first use) for publisher keys.

The index pins every file's sha256 and minisign signs the manifest, but the
publisher's pubkey itself travels in the index. If an index host is ever
compromised or coerced, both the entry and the key can be swapped together
and naive verification still passes.

Defenses, two layers:

1. Official orgs: an offline ROOT key (pinned in this package) signs
   operators.json, the set of online operator keys allowed to sign entries.
   Any operator key works, so the org survives losing any one operator,
   machine, or person. operators.json sits next to index.json at whatever
   host the index came from; a missing file falls back to root-only trust.
2. Everyone else: remember each publisher org's key the first time you see
   it, and fail loudly if it ever changes. Same model as SSH host keys.
   The store is ~/.unmuzzle/known_publishers.json (UNMUZZLE_TRUST_STORE).
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Optional

from . import sign as signmod

DEFAULT_STORE = Path.home() / ".unmuzzle" / "known_publishers.json"

# Official root keys, shipped inside the package itself. This is the trust
# bootstrap: an independent distribution channel no index host can touch.
# Root keys do not sign model entries directly; they sign operators.json.
OFFICIAL_KEYS = {
    "unmuzzle": "RWQGj//qSw5zlf6EB/sSfp8thdSO5ZBr+5pAC9bGhjjReQZ+PLs4gF4K",
}


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


# --- operator set (root-signed) ---------------------------------------------

def canonical_operators_payload(doc: dict) -> str:
    """Deterministic string the root key signs for operators.json."""
    payload = {k: doc[k] for k in ("version", "root_pubkey", "operators") if k in doc}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def verify_operators(doc: dict) -> dict:
    """Verify a decoded operators.json against a trusted root. Returns {name: pubkey}."""
    if not isinstance(doc, dict) or not isinstance(doc.get("operators"), dict) or not doc["operators"]:
        raise KeyChangedError("operators.json: malformed or empty")
    root = doc.get("root_pubkey")
    if root not in set(OFFICIAL_KEYS.values()):
        raise KeyChangedError("operators.json: untrusted root key")
    if not doc.get("signature"):
        raise KeyChangedError("operators.json: unsigned")
    if not signmod.verify(canonical_operators_payload(doc), doc["signature"], root):
        raise KeyChangedError("operators.json: ROOT SIGNATURE INVALID")
    return dict(doc["operators"])


def load_operators(index_source: Optional[str]) -> Optional[dict]:
    """Fetch operators.json next to the index. None if absent (root-only trust);
    a present-but-forged file is a hard error."""
    if not index_source:
        return None
    if index_source.startswith(("http://", "https://")):
        from .download import USER_AGENT
        url = index_source.rsplit("/", 1)[0] + "/operators.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status != 200:
                    return None
                doc = json.loads(r.read().decode())
        except Exception:
            return None
    else:
        p = Path(index_source).parent / "operators.json"
        if not p.exists():
            return None
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
    return verify_operators(doc)


def check_continuity(entry_name: str, pubkey: str, accept_new: bool = False,
                     operators: Optional[dict] = None) -> dict:
    """Pin the publisher's key on first sight; raise KeyChangedError if it
    changes. For official orgs, trust is the root-signed operator set."""
    path = store_path()
    known = _load(path)
    pub = publisher_id(entry_name)

    official = OFFICIAL_KEYS.get(pub)
    if official:
        valid = set(operators.values()) if operators else {official}
        if pubkey not in valid:
            raise KeyChangedError(
                f"WRONG KEY for official publisher {pub}!\n"
                f"  index says: {pubkey}\n"
                f"  trusted operators: {sorted(valid)}\n"
                "The signing key is neither a root key nor in the root-signed "
                "operator set. Do not proceed."
            )
        return {"publisher": pub, "continuity": "ok", "pinned": False, "operator": True}

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
