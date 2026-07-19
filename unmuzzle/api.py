"""Programmatic API for agents.

Agents (Claude Code, Codex, Kimi Code, MCP clients) should call these
functions, or the MCP server in unmuzzle.mcp_server, instead of scraping
CLI output. Every function returns plain JSON-serializable dicts and raises
UnmuzzleError with a machine-actionable message.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from . import hfcache, sign as signmod, trust
from .download import DownloadError, download_file, download_torrent, sha256_file
from .index import ModelEntry, find_model, load_index
from .publish import build_entry, write_entry


class UnmuzzleError(Exception):
    pass


def _entry_dict(e: ModelEntry) -> dict:
    d = dict(e.raw) if e.raw else {}
    d.update({
        "name": e.name,
        "description": e.description,
        "base_model": e.base_model,
        "license": e.license,
        "tags": e.tags,
        "files": e.files,
        "total_size": e.total_size,
        "mirrors": {"http": e.http, "magnet": e.magnet, "torrent": e.torrent},
        "signed": bool(e.signature),
        "revision": e.revision(),
    })
    return d


def _find(name: str, index: Optional[str]) -> ModelEntry:
    entry = find_model(load_index(index), name)
    if not entry:
        raise UnmuzzleError(f"not found: {name}")
    return entry


def list_models(tag: Optional[str] = None, index: Optional[str] = None) -> List[dict]:
    entries = load_index(index)
    if tag:
        entries = [e for e in entries if tag in e.tags]
    return [_entry_dict(e) for e in entries]


def model_info(name: str, index: Optional[str] = None) -> dict:
    return _entry_dict(_find(name, index))


def check_signature(entry: ModelEntry, require: bool = False,
                    accept_new_key: bool = False) -> dict:
    """Verify the entry's minisign signature. Returns a status dict; raises if invalid."""
    if not entry.signature:
        if require:
            raise UnmuzzleError(f"{entry.name} is unsigned and signature was required")
        return {"signed": False, "verified": False}
    if not entry.publisher_pubkey:
        raise UnmuzzleError("entry has a signature but no publisher_pubkey")
    if not signmod.have_minisign():
        if require:
            raise UnmuzzleError("minisign not installed, cannot verify (brew install minisign)")
        return {"signed": True, "verified": False, "warning": "minisign not installed, skipped"}
    if not signmod.verify(entry.canonical_manifest(), entry.signature, entry.publisher_pubkey):
        raise UnmuzzleError(f"SIGNATURE INVALID for {entry.name}")
    result = {"signed": True, "verified": True}
    try:
        result["trust"] = trust.check_continuity(entry.name, entry.publisher_pubkey,
                                                 accept_new=accept_new_key)
    except trust.KeyChangedError as e:
        raise UnmuzzleError(str(e))
    return result


def get(
    name: str,
    dest: Optional[str] = None,
    method: str = "auto",
    jobs: int = 8,
    require_signature: bool = False,
    index: Optional[str] = None,
    accept_new_key: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """Download a model. Returns {revision, method, path, hf_cache, files, bytes}."""
    entry = _find(name, index)
    sig = check_signature(entry, require_signature, accept_new_key=accept_new_key)

    if method == "auto":
        if (entry.torrent or entry.magnet) and shutil.which("aria2c"):
            method = "torrent"
        elif entry.http:
            method = "http"
        elif entry.torrent or entry.magnet:
            method = "torrent"
        else:
            raise UnmuzzleError("entry has no usable mirrors")
    if method == "torrent" and not (entry.torrent or entry.magnet):
        raise UnmuzzleError("entry has no torrent or magnet link")
    if method == "http" and not entry.http:
        raise UnmuzzleError("entry has no http mirrors")

    revision = entry.revision()
    if dest:
        root = Path(dest)
    else:
        root = hfcache.model_cache_dir(entry.name) / ".staging" / revision
    root.mkdir(parents=True, exist_ok=True)

    try:
        if method == "torrent":
            download_torrent(entry.torrent or entry.magnet, root)
            for f in entry.files:
                p = root / f["path"]
                if not p.exists() or sha256_file(p) != f["sha256"]:
                    raise UnmuzzleError(f"{f['path']}: sha256 mismatch after torrent download")
        else:
            for f in entry.files:
                if progress:
                    progress(f"downloading {f['path']}")
                download_file(entry.http, f["path"], root / f["path"], f["size"], f["sha256"],
                              jobs=jobs, progress=progress)
    except DownloadError as e:
        raise UnmuzzleError(str(e))

    result = {
        "name": entry.name,
        "revision": revision,
        "method": method,
        "files": len(entry.files),
        "bytes": entry.total_size,
        "signature": sig,
    }
    if dest:
        result.update(path=str(root), hf_cache=False)
    else:
        snapshot = hfcache.install(entry.name, revision, root, entry.files)
        shutil.rmtree(root, ignore_errors=True)
        result.update(path=str(snapshot), hf_cache=True)
        result["load_with"] = (
            f'from transformers import AutoModelForCausalLM; '
            f'model = AutoModelForCausalLM.from_pretrained("{entry.name}", local_files_only=True)'
        )
    return result


def publish(
    directory: str,
    name: str,
    http_bases: Optional[List[str]] = None,
    magnet: Optional[str] = None,
    torrent_url: Optional[str] = None,
    description: str = "",
    base_model: str = "",
    license: str = "",
    tags: Optional[List[str]] = None,
    sign_key: Optional[str] = None,
    pubkey: Optional[str] = None,
    index_dir: str = "index",
) -> dict:
    """Hash a local model dir, optionally sign, and add it to a local index."""
    entry = build_entry(
        directory=Path(directory), name=name, http_bases=list(http_bases or []),
        magnet=magnet, torrent_url=torrent_url, description=description,
        base_model=base_model,
        license_=license, tags=list(tags or []),
        secret_key=Path(sign_key) if sign_key else None, pubkey=pubkey,
    )
    path = write_entry(Path(index_dir), entry)
    return {
        "entry": entry,
        "entry_path": str(path),
        "index": str(Path(index_dir) / "index.json"),
        "signed": bool(entry.get("signature")),
    }


def verify(name: str, index: Optional[str] = None) -> dict:
    """Re-hash an installed model against the index."""
    entry = _find(name, index)
    snapshot = hfcache.model_cache_dir(entry.name) / "snapshots" / entry.revision()
    if not snapshot.exists():
        raise UnmuzzleError(f"not installed: {entry.name}")
    bad = []
    for f in entry.files:
        p = snapshot / f["path"]
        if not (p.exists() and sha256_file(p) == f["sha256"]):
            bad.append(f["path"])
    return {"name": entry.name, "ok": not bad, "bad_files": bad,
            "checked": len(entry.files), "path": str(snapshot)}


def keygen(key_path: Optional[str] = None) -> dict:
    """Generate a minisign keypair for signing releases. Non-interactive."""
    if not signmod.have_minisign():
        raise UnmuzzleError("minisign not installed (brew install minisign / apt install minisign)")
    secret = Path(key_path or Path.home() / ".minisign" / "unmuzzle.key")
    pub = secret.with_suffix(".pub")
    if secret.exists():
        raise UnmuzzleError(f"key already exists: {secret}")
    secret.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["minisign", "-G", "-W", "-s", str(secret), "-p", str(pub)],
                   check=True, capture_output=True)
    return {"secret_key": str(secret), "public_key": str(pub),
            "pubkey": signmod.pubkey_from_secret(secret)}
