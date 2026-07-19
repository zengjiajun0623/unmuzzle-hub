"""unmuzzle command line interface."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import __version__, hfcache, sign as signmod
from .download import DownloadError, download_file, download_magnet, sha256_file
from .index import IndexError, find_model, load_index
from .publish import build_entry, write_entry


def _fmt_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def cmd_list(args) -> int:
    entries = load_index(args.index)
    if args.tag:
        entries = [e for e in entries if args.tag in e.tags]
    if not entries:
        print("index is empty. Publish a model with `unmuzzle publish`.")
        return 0
    for e in entries:
        sig = " [signed]" if e.signature else ""
        tags = f"  ({', '.join(e.tags)})" if e.tags else ""
        print(f"{e.name:<44} {_fmt_size(e.total_size):>10}{sig}{tags}")
    return 0


def cmd_info(args) -> int:
    entry = find_model(load_index(args.index), args.model)
    if not entry:
        print(f"not found: {args.model}", file=sys.stderr)
        return 1
    print(f"name:        {entry.name}")
    if entry.description:
        print(f"description: {entry.description}")
    if entry.base_model:
        print(f"base model:  {entry.base_model}")
    if entry.license:
        print(f"license:     {entry.license}")
    print(f"revision:    {entry.revision()}")
    print(f"total size:  {_fmt_size(entry.total_size)}")
    print(f"mirrors:     {len(entry.http)} http" + (", 1 torrent" if entry.magnet else ""))
    print(f"signature:   {'yes' if entry.signature else 'no'}")
    print("files:")
    for f in entry.files:
        print(f"  {_fmt_size(f['size']):>10}  {f['path']}")
    return 0


def _verify_signature(entry, require: bool) -> bool:
    if not entry.signature:
        if require:
            print(f"error: {entry.name} is unsigned and --require-signature was given", file=sys.stderr)
            sys.exit(1)
        return False
    if not entry.publisher_pubkey:
        print("error: entry has a signature but no publisher_pubkey", file=sys.stderr)
        sys.exit(1)
    if not signmod.have_minisign():
        if require:
            print("error: minisign not installed, cannot verify. brew install minisign", file=sys.stderr)
            sys.exit(1)
        print("warning: minisign not installed, skipping signature verification", file=sys.stderr)
        return False
    if not signmod.verify(entry.canonical_manifest(), entry.signature, entry.publisher_pubkey):
        print(f"error: SIGNATURE INVALID for {entry.name}. Aborting.", file=sys.stderr)
        sys.exit(1)
    print("signature: OK")
    return True


def cmd_get(args) -> int:
    entry = find_model(load_index(args.index), args.model)
    if not entry:
        print(f"not found: {args.model}", file=sys.stderr)
        return 1
    _verify_signature(entry, args.require_signature)

    method = args.method
    if method == "auto":
        if entry.magnet and shutil.which("aria2c"):
            method = "torrent"
        elif entry.http:
            method = "http"
        elif entry.magnet:
            method = "torrent"  # will error with install advice
        else:
            print("error: entry has no usable mirrors", file=sys.stderr)
            return 1

    revision = entry.revision()
    if args.dest:
        root = Path(args.dest)
    else:
        root = hfcache.model_cache_dir(entry.name) / ".staging" / revision
    root.mkdir(parents=True, exist_ok=True)

    try:
        if method == "torrent":
            if not entry.magnet:
                print("error: entry has no magnet link", file=sys.stderr)
                return 1
            download_magnet(entry.magnet, root)
            # torrent contents are not piece-verified against our index, so re-hash
            for f in entry.files:
                p = root / f["path"]
                if not p.exists() or sha256_file(p) != f["sha256"]:
                    raise DownloadError(f"{f['path']}: sha256 mismatch after torrent download")
        else:
            if not entry.http:
                print("error: entry has no http mirrors", file=sys.stderr)
                return 1
            for f in entry.files:
                print(f"downloading {f['path']} ({_fmt_size(f['size'])})")
                download_file(
                    entry.http, f["path"], root / f["path"], f["size"], f["sha256"],
                    jobs=args.jobs, progress=print,
                )
    except DownloadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.dest:
        print(f"\ndone. Files in {root}")
    else:
        snapshot = hfcache.install(entry.name, revision, root, entry.files)
        shutil.rmtree(root, ignore_errors=True)
        print(f"\ninstalled into HF cache: {snapshot}")
        print(f"\nload it with:")
        print(f'  from transformers import AutoModelForCausalLM')
        print(f'  model = AutoModelForCausalLM.from_pretrained("{entry.name}", local_files_only=True)')
    return 0


def cmd_publish(args) -> int:
    entry = build_entry(
        directory=Path(args.dir),
        name=args.name,
        http_bases=args.http_base or [],
        magnet=args.magnet,
        description=args.description or "",
        base_model=args.base_model or "",
        license_=args.license or "",
        tags=args.tag or [],
        secret_key=Path(args.sign_key) if args.sign_key else None,
        pubkey=args.pubkey,
    )
    index_dir = Path(args.index_dir)
    path = write_entry(index_dir, entry)
    print(f"wrote {path}")
    print(f"regenerated {index_dir / 'index.json'}")
    if not entry.get("signature"):
        print("note: entry is unsigned. Use --sign-key to sign releases.")
    print("\nnext: upload the model files to your mirror(s), then commit and push the index.")
    return 0


def cmd_verify(args) -> int:
    entry = find_model(load_index(args.index), args.model)
    if not entry:
        print(f"not found: {args.model}", file=sys.stderr)
        return 1
    snapshot = hfcache.model_cache_dir(entry.name) / "snapshots" / entry.revision()
    if not snapshot.exists():
        print(f"not installed: {entry.name}", file=sys.stderr)
        return 1
    bad = 0
    for f in entry.files:
        p = snapshot / f["path"]
        ok = p.exists() and sha256_file(p) == f["sha256"]
        print(f"{'ok ' if ok else 'BAD'}  {f['path']}")
        bad += 0 if ok else 1
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="unmuzzle",
        description="Censorship-resistant distribution for open-weight models.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_index_arg(sp):
        sp.add_argument("--index", default=None,
                        help="index URL or local path (default: $UNMUZZLE_INDEX or the unmuzzle index)")

    sp = sub.add_parser("list", help="list models in the index")
    sp.add_argument("--tag", help="filter by tag")
    add_index_arg(sp)
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("info", help="show files, mirrors, and signature for a model")
    sp.add_argument("model")
    add_index_arg(sp)
    sp.set_defaults(fn=cmd_info)

    sp = sub.add_parser("get", help="download a model and install it into the HF cache")
    sp.add_argument("model")
    sp.add_argument("--dest", help="download plain files to this directory instead of the HF cache")
    sp.add_argument("--method", choices=["auto", "http", "torrent"], default="auto")
    sp.add_argument("--jobs", type=int, default=8, help="parallel chunks per file (http)")
    sp.add_argument("--require-signature", action="store_true",
                    help="abort unless the entry has a valid minisign signature")
    add_index_arg(sp)
    sp.set_defaults(fn=cmd_get)

    sp = sub.add_parser("publish", help="hash a local model dir and add it to a local index")
    sp.add_argument("dir", help="directory containing the model files")
    sp.add_argument("--name", required=True, help="org/name")
    sp.add_argument("--http-base", action="append", help="base URL where files will be served (repeatable)")
    sp.add_argument("--magnet", help="magnet link for the torrent of this directory")
    sp.add_argument("--description")
    sp.add_argument("--base-model")
    sp.add_argument("--license")
    sp.add_argument("--tag", action="append", help="tag (repeatable)")
    sp.add_argument("--sign-key", help="minisign secret key to sign the manifest")
    sp.add_argument("--pubkey", help="publisher pubkey (base64); derived from --sign-key if omitted")
    sp.add_argument("--index-dir", default="index", help="local index directory to update")
    sp.set_defaults(fn=cmd_publish)

    sp = sub.add_parser("verify", help="re-hash an installed model against the index")
    sp.add_argument("model")
    add_index_arg(sp)
    sp.set_defaults(fn=cmd_verify)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except IndexError as e:
        print(f"index error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
