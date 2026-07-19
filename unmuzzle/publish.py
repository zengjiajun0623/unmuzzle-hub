"""Build index entries from a local model directory (`unmuzzle publish`)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import List, Optional

from .download import sha256_file
from .index import validate_entry
from . import sign as signmod

SKIP_NAMES = {".DS_Store"}
SKIP_SUFFIXES = (".parts", ".tmp")


def _iter_model_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if p.name in SKIP_NAMES or any(rel.endswith(s) for s in SKIP_SUFFIXES):
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        yield rel, p


def build_entry(
    directory: Path,
    name: str,
    http_bases: List[str],
    magnet: Optional[str] = None,
    description: str = "",
    base_model: str = "",
    license_: str = "",
    tags: Optional[List[str]] = None,
    secret_key: Optional[Path] = None,
    pubkey: Optional[str] = None,
) -> dict:
    directory = Path(directory)
    files = []
    for rel, p in _iter_model_files(directory):
        files.append({"path": rel, "size": p.stat().st_size, "sha256": sha256_file(p)})
    if not files:
        raise ValueError(f"no model files found in {directory}")

    entry = {
        "name": name,
        "description": description,
        "base_model": base_model,
        "license": license_,
        "tags": tags or [],
        "added": date.today().isoformat(),
        "files": files,
        "mirrors": {"http": http_bases, "magnet": magnet},
    }

    if secret_key:
        manifest = validate_entry(entry).canonical_manifest()
        entry["signature"] = signmod.sign(manifest, Path(secret_key))
        entry["publisher_pubkey"] = pubkey or signmod.pubkey_from_secret(Path(secret_key))

    validate_entry(entry)  # final sanity check
    return entry


def write_entry(index_dir: Path, entry: dict) -> Path:
    """Write one entry file and regenerate the combined index.json."""
    index_dir = Path(index_dir)
    models_dir = index_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    slug = entry["name"].replace("/", "__")
    (models_dir / f"{slug}.json").write_text(json.dumps(entry, indent=2) + "\n")
    regenerate(index_dir)
    return models_dir / f"{slug}.json"


def regenerate(index_dir: Path) -> Path:
    models_dir = Path(index_dir) / "models"
    entries = []
    if models_dir.exists():
        for f in sorted(models_dir.glob("*.json")):
            entries.append(json.loads(f.read_text()))
    out = Path(index_dir) / "index.json"
    out.write_text(json.dumps({"version": 1, "models": entries}, indent=2) + "\n")
    return out
