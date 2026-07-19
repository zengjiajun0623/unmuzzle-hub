"""Parallel ranged HTTP downloads with resume, plus magnet links via aria2c.

HTTP downloads split each file into fixed-size chunks fetched with Range
requests from any of the entry's mirrors. Chunks land in a .parts directory
next to the target, so an interrupted download resumes where it stopped.
Every completed file is verified against the sha256 from the index before
it is moved into place.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

DEFAULT_CHUNK = 32 * 1024 * 1024  # 32 MiB

# Cloudflare-fronted mirrors (R2) 403 the default Python-urllib UA.
USER_AGENT = "unmuzzle/0 (+https://github.com/zengjiajun0623/unmuzzle-hub)"


class DownloadError(Exception):
    pass


def _fetch_range(url: str, start: int, end: int, dest: Path, retries: int = 4) -> None:
    want = end - start + 1
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}",
                                                       "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            if dest.stat().st_size == want:
                return
        except Exception:
            if attempt == retries - 1:
                raise
    raise DownloadError(f"range {start}-{end} from {url}: incomplete after {retries} tries")


def sha256_file(path: Path, buf: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(buf), b""):
            h.update(block)
    return h.hexdigest()


def download_file(
    base_urls: List[str],
    relpath: str,
    dest: Path,
    size: int,
    sha256: str,
    jobs: int = 8,
    chunk_size: int = DEFAULT_CHUNK,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Fetch one file from any of base_urls (base + '/' + relpath), verify sha256."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == size and sha256_file(dest) == sha256:
        return dest  # already have it, verified

    urls = [f"{base.rstrip('/')}/{relpath}" for base in base_urls]
    parts_dir = dest.parent / (dest.name + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)

    n_chunks = max(1, (size + chunk_size - 1) // chunk_size)
    todo = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = min(size - 1, start + chunk_size - 1)
        part = parts_dir / f"{i:06d}"
        if part.exists() and part.stat().st_size == end - start + 1:
            continue  # resume: chunk already done
        todo.append((i, start, end, part))

    def work(t):
        i, start, end, part = t
        last_err: Optional[Exception] = None
        for url in urls:
            try:
                _fetch_range(url, start, end, part)
                return i
            except Exception as e:  # try next mirror
                last_err = e
        raise DownloadError(f"{relpath} chunk {i}: all mirrors failed ({last_err})")

    done = n_chunks - len(todo)
    if todo:
        with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
            for _ in ex.map(work, todo):
                done += 1
                if progress:
                    progress(f"  {relpath}: {done}/{n_chunks} chunks")

    tmp = dest.with_name(dest.name + ".tmp")
    h = hashlib.sha256()
    with open(tmp, "wb") as out:
        for i in range(n_chunks):
            with open(parts_dir / f"{i:06d}", "rb") as p:
                while True:
                    block = p.read(8 * 1024 * 1024)
                    if not block:
                        break
                    h.update(block)
                    out.write(block)
    if h.hexdigest() != sha256:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(parts_dir, ignore_errors=True)
        raise DownloadError(f"{relpath}: sha256 mismatch (expected {sha256})")
    if tmp.stat().st_size != size:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"{relpath}: size mismatch (expected {size})")
    tmp.replace(dest)
    shutil.rmtree(parts_dir, ignore_errors=True)
    return dest


def download_torrent(uri_or_file: str, dest_dir: Path) -> None:
    """Fetch a torrent (magnet URI, .torrent URL, or local .torrent path) into
    dest_dir using aria2c. Seeding is left to the user.

    Prefer .torrent files over bare magnets when web seeds are the only
    guaranteed source: a magnet still needs a reachable peer to fetch the
    metadata, a .torrent plus a web seed works with zero peers.
    """
    if not shutil.which("aria2c"):
        raise DownloadError(
            "torrent downloads need aria2c (brew install aria2 / apt install aria2), "
            "or retry with --method http"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["aria2c", "--seed-time=0", "--summary-interval=30", "-d", str(dest_dir), uri_or_file],
        check=True,
    )
