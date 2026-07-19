"""minisign-based signing of manifests.

The publisher signs the canonical manifest (sha256 + path per file) with
minisign (OpenBSD signify compatible). Clients verify before installing.
minisign is a single static binary: brew install minisign.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


class SignatureError(Exception):
    pass


def have_minisign() -> bool:
    return shutil.which("minisign") is not None


def pubkey_from_secret(secret_key: Path) -> str:
    """Derive the base64 public key from a secret key via `minisign -R`."""
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "key.pub"
        subprocess.run(
            ["minisign", "-R", "-s", str(secret_key), "-p", str(pub)],
            check=True, capture_output=True,
        )
        lines = pub.read_text().splitlines()
    for line in lines:
        line = line.strip()
        if line and not line.startswith("untrusted comment"):
            return line
    raise SignatureError(f"could not parse pubkey from {pub!r}")


def sign(manifest: str, secret_key: Path) -> str:
    with tempfile.TemporaryDirectory() as td:
        msg = Path(td) / "manifest.txt"
        sig = Path(td) / "manifest.txt.minisig"
        msg.write_text(manifest)
        subprocess.run(
            ["minisign", "-S", "-s", str(secret_key), "-x", str(sig), "-m", str(msg)],
            check=True, capture_output=True,
        )
        return sig.read_text()


def verify(manifest: str, signature: str, pubkey_b64: str) -> bool:
    if not have_minisign():
        raise SignatureError("minisign not installed, cannot verify signature")
    with tempfile.TemporaryDirectory() as td:
        msg = Path(td) / "manifest.txt"
        sig = Path(td) / "manifest.txt.minisig"
        msg.write_text(manifest)
        sig.write_text(signature)
        r = subprocess.run(
            ["minisign", "-V", "-P", pubkey_b64, "-x", str(sig), "-m", str(msg)],
            capture_output=True,
        )
        return r.returncode == 0
