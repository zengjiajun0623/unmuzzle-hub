#!/usr/bin/env python3
"""End-to-end verification loop for published unmuzzle releases.

Tier 1 (always, seconds): the published index parses and every entry's
minisign signature verifies; every HTTP mirror answers a Range probe with
the manifest's byte size; the .torrent URL is live and its infohash matches
the magnet; trackers report the swarm's seeder count.

Tier 2 (--full, minutes): a real `unmuzzle get --require-signature` for
each entry, into a temp dir that is deleted after. This is the AGENTS.md
"verify your publication" flow, automated. Note: --method http needs 2x
the model size free on disk (parts + concat); torrent needs 1x.

Exit 0 = all hard checks passed. Warnings (e.g. zero seeders, an
unreachable tracker) are printed but do not fail the run, because the
web seed keeps every torrent alive at zero peers by design.

Usage:
  python3 scripts/verify_release.py [--full] [--method http|torrent|both]
                                    [--index URL] [--json]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unmuzzle import api  # noqa: E402
from unmuzzle.download import USER_AGENT  # noqa: E402
from unmuzzle.index import load_index  # noqa: E402

REPORT = []


def check(name: str, ok: bool, detail: str = "", warn: bool = False) -> bool:
    status = "pass" if ok else ("warn" if warn else "FAIL")
    REPORT.append({"check": name, "status": status, "detail": detail})
    print(f"[{status:>4}] {name}" + (f" -- {detail}" if detail else ""))
    return ok


# --- bencode (enough to read a .torrent and hash its info dict) -------------

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


def torrent_infohash(torrent_bytes: bytes) -> bytes:
    """sha1 of the raw bencoded info dict (the btih)."""
    i = 1  # top-level dict
    while torrent_bytes[i:i + 1] != b"e":
        k, i = _bdecode(torrent_bytes, i)
        v_start = i
        _, i = _bdecode(torrent_bytes, i)
        if k == b"info":
            return hashlib.sha1(torrent_bytes[v_start:i]).digest()
    raise ValueError("no info dict in torrent")


def btih_from_magnet(magnet: str) -> bytes:
    xt = urllib.parse.parse_qs(urllib.parse.urlparse(magnet).query)["xt"][0]
    h = xt.rsplit(":", 1)[-1]
    if len(h) == 40:
        return bytes.fromhex(h)
    return base64.b32decode(h)  # 32-char base32 form


# --- UDP tracker announce (BEP 15), returns (seeders, leechers) --------------

def tracker_swarm(tracker: str, infohash: bytes, timeout: float = 8.0):
    u = urllib.parse.urlparse(tracker)
    if u.scheme != "udp":
        return None
    addr = (u.hostname, u.port or 80)
    txn = struct.unpack(">I", hashlib.sha1(struct.pack(">I", os.getpid())).digest()[:4])[0]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(struct.pack(">QII", 0x41727101980, 0, txn), addr)
        resp, _ = s.recvfrom(2048)
        if len(resp) < 16 or struct.unpack(">I", resp[:4])[0] != 0:
            raise OSError("bad connect response")
        conn_id = struct.unpack(">Q", resp[8:16])[0]
        peer_id = b"-UM0001-" + hashlib.sha1(b"unmuzzle-verify").digest()[:12]
        s.sendto(struct.pack(">QII20s20sQQQIIIiH", conn_id, 1, txn, infohash, peer_id,
                             0, 0, 0, 0, 0, 0, 50, 6881), addr)
        resp, _ = s.recvfrom(2048)
        if len(resp) < 20 or struct.unpack(">I", resp[:4])[0] != 1:
            raise OSError("bad announce response")
        _, _, interval, leechers, seeders = struct.unpack(">IIIII", resp[:20])
        return seeders, leechers


# --- probes ------------------------------------------------------------------

def probe_http_file(base: str, path: str, size: int) -> str:
    """One 1-byte Range GET; expects 206 and the manifest's total size."""
    url = f"{base.rstrip('/')}/{urllib.parse.quote(path)}"
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0",
                                               "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 206:
            raise OSError(f"expected 206, got {r.status}")
        total = int(r.headers["Content-Range"].rsplit("/", 1)[-1])
        if total != size:
            raise OSError(f"size mismatch: mirror {total} vs manifest {size}")
    return url


def probe_entry(entry, full: bool, methods) -> bool:
    ok = True
    sig = api.check_signature(entry, require=True)
    ok &= check(f"{entry.name}: signature", sig.get("verified") is True)

    for f in entry.files:
        for base in entry.http:
            try:
                url = probe_http_file(base, f["path"], f["size"])
                check(f"{entry.name}: http range probe {f['path']}", True, url)
            except Exception as e:
                ok &= check(f"{entry.name}: http range probe {f['path']}", False, str(e))

    infohash = None
    if entry.torrent:
        try:
            with urllib.request.urlopen(entry.torrent, timeout=60) as r:
                tb = r.read()
            infohash = torrent_infohash(tb)
            check(f"{entry.name}: torrent url", True, f"{len(tb)} bytes")
            if entry.magnet:
                want = btih_from_magnet(entry.magnet)
                ok &= check(f"{entry.name}: torrent matches magnet infohash", infohash == want,
                            infohash.hex())
        except Exception as e:
            ok &= check(f"{entry.name}: torrent url", False, str(e))

    if entry.magnet:
        trackers = urllib.parse.parse_qs(urllib.parse.urlparse(entry.magnet).query).get("tr", [])
        ih = infohash or btih_from_magnet(entry.magnet)
        seeders_total, answered = 0, 0
        for t in trackers:
            try:
                swarm = tracker_swarm(t, ih)
            except Exception:
                swarm = None
            if swarm:
                answered += 1
                seeders_total += swarm[0]
                check(f"{entry.name}: tracker {t}", True,
                      f"{swarm[0]} seeders, {swarm[1]} leechers", warn=swarm[0] == 0)
            else:
                check(f"{entry.name}: tracker {t}", True, "no answer (udp tracker)", warn=True)
        if answered:
            check(f"{entry.name}: swarm has seeders", seeders_total > 0,
                  f"{seeders_total} across {answered} trackers", warn=seeders_total == 0)

    if full:
        for m in methods:
            dest = tempfile.mkdtemp(prefix=f"um-verify-{m}-")
            try:
                print(f"  ... full download via {m} into {dest}")
                r = subprocess.run(
                    [sys.executable, "-m", "unmuzzle.cli", "get", entry.name,
                     "--method", m, "--require-signature", "--dest", dest, "--json"],
                    capture_output=True, text=True, timeout=7200,
                    cwd=Path(__file__).resolve().parent.parent)
                if r.returncode == 0:
                    out = json.loads(r.stdout)
                    check(f"{entry.name}: FULL e2e via {m}", True,
                          f"{out['bytes']} bytes, signature={out['signature']}")
                else:
                    ok &= check(f"{entry.name}: FULL e2e via {m}", False,
                                (r.stderr or r.stdout).strip()[-400:])
            finally:
                shutil.rmtree(dest, ignore_errors=True)
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--full", action="store_true", help="also do real downloads (tier 2)")
    p.add_argument("--method", choices=["http", "torrent", "both"], default="both")
    p.add_argument("--index", default=None, help="index URL/path (default: canonical)")
    p.add_argument("--json", action="store_true", help="print JSON report at the end")
    args = p.parse_args()

    try:
        entries = load_index(args.index)
    except Exception as e:
        check("index fetch/parse", False, str(e))
        return 1
    src = args.index or "canonical (DEFAULT_INDEX)"
    check("index fetch/parse", True, f"{len(entries)} entries from {src}")

    ok = True
    methods = ["http", "torrent"] if args.method == "both" else [args.method]
    for entry in entries:
        try:
            ok &= probe_entry(entry, args.full, methods)
        except api.UnmuzzleError as e:
            ok &= check(f"{entry.name}", False, str(e))

    n_fail = sum(1 for r in REPORT if r["status"] == "FAIL")
    n_warn = sum(1 for r in REPORT if r["status"] == "warn")
    print(f"\n== {'FAIL' if n_fail else 'PASS'}: "
          f"{len(REPORT) - n_fail - n_warn} passed, {n_warn} warnings, {n_fail} failed ==")
    if args.json:
        print(json.dumps({"ok": not n_fail, "checks": REPORT}, indent=2))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
