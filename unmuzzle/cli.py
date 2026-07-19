"""unmuzzle command line interface.

Thin wrapper over unmuzzle.api. All output is human-readable by default and
JSON with --json, so agents can drive everything non-interactively.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, api


def _fmt_size(n) -> str:
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n} B"


def _emit(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))


def cmd_list(args) -> int:
    models = api.list_models(tag=args.tag, index=args.index)
    _emit(models, args.json)
    if not args.json:
        if not models:
            print("index is empty. Publish a model with `unmuzzle publish`.")
        for m in models:
            sig = " [signed]" if m["signed"] else ""
            tags = f"  ({', '.join(m['tags'])})" if m["tags"] else ""
            print(f"{m['name']:<44} {_fmt_size(m['total_size']):>10}{sig}{tags}")
    return 0


def cmd_info(args) -> int:
    m = api.model_info(args.model, index=args.index)
    _emit(m, args.json)
    if not args.json:
        print(f"name:        {m['name']}")
        for label, key in (("description", "description"), ("base model", "base_model"),
                           ("license", "license")):
            if m.get(key):
                print(f"{label + ':':<13}{m[key]}")
        print(f"revision:    {m['revision']}")
        print(f"total size:  {_fmt_size(m['total_size'])}")
        print(f"mirrors:     {len(m['mirrors']['http'])} http"
              + (", 1 torrent" if m["mirrors"]["magnet"] else ""))
        print(f"signature:   {'yes' if m['signed'] else 'no'}")
        print("files:")
        for f in m["files"]:
            print(f"  {_fmt_size(f['size']):>10}  {f['path']}")
    return 0


def cmd_get(args) -> int:
    progress = (lambda s: print(s, file=sys.stderr)) if args.json else print
    result = api.get(
        args.model, dest=args.dest, method=args.method, jobs=args.jobs,
        require_signature=args.require_signature, index=args.index,
        progress=progress,
    )
    _emit(result, args.json)
    if not args.json:
        if result["signature"].get("verified"):
            print("signature: OK")
        if result["hf_cache"]:
            print(f"\ninstalled into HF cache: {result['path']}")
            print(f"\nload it with:\n  {result['load_with']}")
        else:
            print(f"\ndone. Files in {result['path']}")
    return 0


def cmd_publish(args) -> int:
    result = api.publish(
        directory=args.dir, name=args.name, http_bases=args.http_base,
        magnet=args.magnet, torrent_url=args.torrent_url,
        description=args.description or "",
        base_model=args.base_model or "", license=args.license or "",
        tags=args.tag, sign_key=args.sign_key, pubkey=args.pubkey,
        index_dir=args.index_dir,
    )
    _emit(result, args.json)
    if not args.json:
        print(f"wrote {result['entry_path']}")
        print(f"regenerated {result['index']}")
        if not result["signed"]:
            print("note: entry is unsigned. Use --sign-key to sign releases.")
        print("\nnext: upload the model files to your mirror(s), then commit and push the index.")
    return 0


def cmd_verify(args) -> int:
    result = api.verify(args.model, index=args.index)
    _emit(result, args.json)
    if not args.json:
        print(f"{'OK' if result['ok'] else 'BAD'}: {result['checked']} files checked at {result['path']}")
    return 0 if result["ok"] else 1


def cmd_keygen(args) -> int:
    result = api.keygen(args.key)
    _emit(result, args.json)
    if not args.json:
        print(f"secret key: {result['secret_key']} (keep it secret, back it up)")
        print(f"public key: {result['public_key']}")
        print(f"pubkey:     {result['pubkey']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="unmuzzle",
        description="Agent-native, censorship-resistant distribution for open-weight models.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, index=False):
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        if index:
            sp.add_argument("--index", default=None,
                            help="index URL or local path (default: $UNMUZZLE_INDEX or the unmuzzle index)")

    sp = sub.add_parser("list", help="list models in the index")
    sp.add_argument("--tag", help="filter by tag")
    common(sp, index=True)
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("info", help="show files, mirrors, and signature for a model")
    sp.add_argument("model")
    common(sp, index=True)
    sp.set_defaults(fn=cmd_info)

    sp = sub.add_parser("get", help="download a model and install it into the HF cache")
    sp.add_argument("model")
    sp.add_argument("--dest", help="download plain files to this directory instead of the HF cache")
    sp.add_argument("--method", choices=["auto", "http", "torrent"], default="auto")
    sp.add_argument("--jobs", type=int, default=8, help="parallel chunks per file (http)")
    sp.add_argument("--require-signature", action="store_true",
                    help="abort unless the entry has a valid minisign signature")
    common(sp, index=True)
    sp.set_defaults(fn=cmd_get)

    sp = sub.add_parser("publish", help="hash a local model dir and add it to a local index")
    sp.add_argument("dir", help="directory containing the model files")
    sp.add_argument("--name", required=True, help="org/name")
    sp.add_argument("--http-base", action="append", help="base URL where files will be served (repeatable)")
    sp.add_argument("--magnet", help="magnet link for the torrent of this directory")
    sp.add_argument("--torrent-url", help="URL of the .torrent file (preferred over magnet: works with zero peers via web seeds)")
    sp.add_argument("--description")
    sp.add_argument("--base-model")
    sp.add_argument("--license")
    sp.add_argument("--tag", action="append", help="tag (repeatable)")
    sp.add_argument("--sign-key", help="minisign secret key to sign the manifest")
    sp.add_argument("--pubkey", help="publisher pubkey (base64); derived from --sign-key if omitted")
    sp.add_argument("--index-dir", default="index", help="local index directory to update")
    common(sp)
    sp.set_defaults(fn=cmd_publish)

    sp = sub.add_parser("verify", help="re-hash an installed model against the index")
    sp.add_argument("model")
    common(sp, index=True)
    sp.set_defaults(fn=cmd_verify)

    sp = sub.add_parser("keygen", help="generate a minisign keypair for signing releases")
    sp.add_argument("--key", help="secret key path (default: ~/.minisign/unmuzzle.key)")
    common(sp)
    sp.set_defaults(fn=cmd_keygen)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except api.UnmuzzleError as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        else:
            print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
