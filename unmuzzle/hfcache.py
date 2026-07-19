"""Install downloaded files into the Hugging Face hub cache layout.

Once installed, `from_pretrained("org/name", local_files_only=True)` loads
the model with zero changes to user code. Blobs are content-addressed by
sha256, snapshots symlink (or copy) into blobs, refs/main points at the
revision.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List


def hf_cache_root() -> Path:
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def model_cache_dir(model_id: str) -> Path:
    return hf_cache_root() / f"models--{model_id.replace('/', '--')}"


def install(model_id: str, revision: str, staging: Path, files: List[dict]) -> Path:
    """Link files from staging into the HF cache. Returns the snapshot path."""
    staging = Path(staging)
    cache = model_cache_dir(model_id)
    blobs = cache / "blobs"
    snapshot = cache / "snapshots" / revision
    refs = cache / "refs"
    for d in (blobs, snapshot, refs):
        d.mkdir(parents=True, exist_ok=True)

    for f in files:
        src = staging / f["path"]
        if not src.exists():
            raise FileNotFoundError(f"missing staged file {src}")
        blob = blobs / f["sha256"]
        if not blob.exists():
            try:
                os.link(src, blob)
            except OSError:
                shutil.copy2(src, blob)
        link = snapshot / f["path"]
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        try:
            os.symlink(os.path.relpath(blob, link.parent), link)
        except OSError:  # filesystem without symlinks
            shutil.copy2(blob, link)

    (refs / "main").write_text(revision)
    return snapshot
