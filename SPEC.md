# unmuzzle index spec (v1)

The index is a JSON document. The canonical one lives in this repo at
`index/index.json` and is generated from `index/models/*.json` (one file per
model, so git diffs stay clean). Clients fetch it over HTTPS or read a local
copy; `--index` and `$UNMUZZLE_INDEX` point at alternatives.

## Top level

```json
{
  "version": 1,
  "models": [ <entry>, ... ]
}
```

## Entry

```json
{
  "name": "unmuzzle/qwen3-8b-truthful",
  "description": "Honesty-SFT of Qwen3-8B. Uncensored, benchmarked.",
  "base_model": "Qwen/Qwen3-8B",
  "license": "apache-2.0",
  "tags": ["uncensored", "chinese", "sft"],
  "added": "2026-07-19",
  "files": [
    {"path": "config.json", "size": 663, "sha256": "..."},
    {"path": "model-00001-of-00003.safetensors", "size": 3999999, "sha256": "..."}
  ],
  "mirrors": {
    "http": ["https://bucket.r2.dev/qwen3-8b-truthful"],
    "torrent": "https://bucket.r2.dev/qwen3-8b-truthful.torrent",
    "magnet": "magnet:?xt=urn:btih:...&ws=https://bucket.r2.dev/qwen3-8b-truthful/"
  },
  "publisher_pubkey": "<minisign base64 pubkey>",
  "signature": "<minisign signature, see below>"
}
```

Rules:

- `name` is `org/name`. File `path` values are relative, no `..`, no leading `/`.
- Every file has `size` (bytes) and `sha256` (hex). Clients MUST verify both
  before installing, regardless of transport.
- `mirrors.http` is a list of base URLs; a file is at `<base>/<path>`. Clients
  try mirrors in order and fail over per chunk.
- `mirrors.magnet` SHOULD include `ws=` web seeds pointing at an HTTP mirror so
  the swarm never dies when seed count hits zero.
- `mirrors.torrent` is a URL of the `.torrent` file itself. Clients prefer it
  over the bare magnet: a magnet still needs one reachable peer to fetch the
  metadata, while a `.torrent` plus a web seed downloads with zero peers.
- Single-file torrents SHOULD use the file's direct URL as the web seed
  (BEP 19), which any static file host can serve.

## Manifest and signature

The signed payload is the **canonical manifest**: one line per file,
`"<sha256>  <path>"`, sorted by path, trailing newline. (Same double-space
convention as `sha256sum` output.)

Publishers sign it with [minisign](https://jedisct1.github.io/minisign/):

```bash
minisign -Sm manifest.txt -s unmuzzle.key -x manifest.txt.minisig
```

The entry embeds the signature file contents in `signature` and the base64
public key in `publisher_pubkey`. Clients verify with
`minisign -V -P <pubkey>`. `--require-signature` aborts on unsigned entries.

## Revision

`revision = sha256(canonical_manifest)[0:16]`. It is the content-addressed
stand-in for an HF commit sha: clients install into
`~/.cache/huggingface/hub/models--<org>--<name>/{blobs,snapshots/<revision>,refs/main}`.
Same weights, same revision, same cache slot, on any machine.

## Threat model

What this protects against:

- **Takedown / geoblocking of a central host.** Index is a git repo, trivially
  mirrored; weights move over torrent + any static host.
- **Poisoned or swapped weights in transit.** Per-file sha256 pinned in the
  index, verified after download.
- **Impersonated publisher.** minisign signature over the manifest. Compromising
  a mirror or the index host does not let an attacker ship different weights
  under the publisher's name.

What it does not protect against:

- A publisher signing malicious weights. Signatures prove origin, not intent.
- The index repo itself being censored from where you are. Mitigation: fork or
  mirror the repo anywhere (it is ~kilobytes) and point `--index` at it.
