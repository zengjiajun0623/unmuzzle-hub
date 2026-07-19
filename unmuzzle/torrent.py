"""Minimal .torrent parsing: enough to learn a torrent's content layout."""
from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from .download import USER_AGENT


def _bdecode(data: bytes, i: int = 0):
    c = data[i:i + 1]
    if c == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1:j]), j + 1
    if c == b"l":
        out, i = [], i + 1
        while data[i:i + 1] != b"e":
            v, i = _bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        out, i = {}, i + 1
        while data[i:i + 1] != b"e":
            k, i = _bdecode(data, i)
            v, i = _bdecode(data, i)
            out[k] = v
        return out, i + 1
    if c.isdigit():
        j = data.index(b":", i)
        n = int(data[i:j])
        return data[j + 1:j + 1 + n], j + 1 + n
    raise ValueError(f"bad bencode at {i}")


def torrent_layout(uri_or_file: str) -> Tuple[str, bool]:
    """Return (root_name, is_multifile): the torrent's top-level name and
    whether it wraps a directory. Single-file torrents return the file name
    and False."""
    if uri_or_file.startswith(("http://", "https://")):
        req = urllib.request.Request(uri_or_file, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    else:
        data = Path(uri_or_file).read_bytes()
    meta, _ = _bdecode(data)
    info = meta[b"info"]
    name = info[b"name"].decode()
    return name, b"files" in info
