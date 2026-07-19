"""Index loading, validation, and manifest canonicalization.

The index is a single JSON document (see SPEC.md). It can live anywhere:
a git repo, static hosting, IPFS. Clients fetch it over HTTPS or read it
from a local path.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

DEFAULT_INDEX = (
    "https://raw.githubusercontent.com/zengjiajun0623/unmuzzle-hub/main/index/index.json"
)


class IndexError(Exception):
    pass


@dataclass
class ModelEntry:
    name: str  # "org/name"
    description: str = ""
    base_model: str = ""
    license: str = ""
    tags: List[str] = field(default_factory=list)
    files: List[dict] = field(default_factory=list)  # {path, size, sha256}
    http: List[str] = field(default_factory=list)  # base URLs, file fetched from base + "/" + path
    magnet: Optional[str] = None
    torrent: Optional[str] = None  # URL of the .torrent file (works with zero peers via web seeds)
    publisher_pubkey: Optional[str] = None
    signature: Optional[str] = None  # minisign signature over canonical_manifest()
    added: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def total_size(self) -> int:
        return sum(f["size"] for f in self.files)

    def canonical_manifest(self) -> str:
        """Deterministic string that gets signed. One 'sha256  path' line per file, sorted."""
        lines = sorted(f'{f["sha256"]}  {f["path"]}' for f in self.files)
        return "\n".join(lines) + "\n"

    def revision(self) -> str:
        """Content-addressed stand-in for an HF commit sha."""
        return hashlib.sha256(self.canonical_manifest().encode()).hexdigest()[:16]


def validate_entry(d: dict) -> ModelEntry:
    if not isinstance(d, dict):
        raise IndexError("entry is not an object")
    name = d.get("name")
    if not name or "/" not in name:
        raise IndexError(f"bad model name: {name!r} (expected 'org/name')")
    files = d.get("files")
    if not files:
        raise IndexError(f"{name}: no files")
    for f in files:
        for key in ("path", "size", "sha256"):
            if key not in f:
                raise IndexError(f"{name}: file entry missing {key!r}: {f!r}")
        parts = Path(f["path"]).parts
        if f["path"].startswith("/") or ".." in parts:
            raise IndexError(f"{name}: unsafe path {f['path']!r}")
        if not isinstance(f["size"], int) or f["size"] < 0:
            raise IndexError(f"{name}: bad size for {f['path']!r}")
        if len(f["sha256"]) != 64:
            raise IndexError(f"{name}: bad sha256 for {f['path']!r}")
    mirrors = d.get("mirrors") or {}
    entry = ModelEntry(
        name=name,
        description=d.get("description", ""),
        base_model=d.get("base_model", ""),
        license=d.get("license", ""),
        tags=list(d.get("tags", [])),
        files=list(files),
        http=list(mirrors.get("http", [])),
        magnet=mirrors.get("magnet"),
        torrent=mirrors.get("torrent"),
        publisher_pubkey=d.get("publisher_pubkey"),
        signature=d.get("signature"),
        added=d.get("added", ""),
        raw=d,
    )
    if not entry.http and not entry.magnet and not entry.torrent:
        raise IndexError(f"{name}: entry has no mirrors")
    return entry


def resolve_index_source(source: Optional[str] = None) -> str:
    return source or os.environ.get("UNMUZZLE_INDEX") or DEFAULT_INDEX


def load_index(source: Optional[str] = None) -> List[ModelEntry]:
    source = resolve_index_source(source)
    if source.startswith(("http://", "https://")):
        # some hosts (Cloudflare-fronted mirrors) 403 the default urllib UA
        from .download import USER_AGENT
        req = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    else:
        data = json.loads(Path(source).read_text())
    entries = data.get("models") if isinstance(data, dict) else data
    return [validate_entry(e) for e in entries]


def find_model(entries: List[ModelEntry], name: str) -> Optional[ModelEntry]:
    for e in entries:
        if e.name == name:
            return e
    # allow shorthand without org if unambiguous
    matches = [e for e in entries if e.name.split("/", 1)[1] == name]
    if len(matches) == 1:
        return matches[0]
    return None
