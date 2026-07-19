# AGENTS.md — runbook for AI agents

You are an agent (Claude Code, Codex, Kimi Code, or an MCP client) and your
user wants to **download** or **publish** an open-weight model. This file is
the complete protocol. Everything here is non-interactive and scriptable.

unmuzzle exists because the alternatives fail agents: Hugging Face gated
models need a human browser login and license click-through, mirrors can be
censored or swapped, and bare torrents have no integrity or discovery story.
Here the index is plain JSON, every file is sha256-pinned, and manifests are
minisign-signed. No auth, no gates, no click-throughs.

## Install

```bash
pip install unmuzzle            # or: pip install git+https://github.com/zengjiajun0623/unmuzzle-hub.git
brew install aria2 minisign     # optional: torrent downloads, signing
```

Every command accepts `--json` and prints machine-readable output on stdout
(progress and errors go to stderr). Parse stdout only.

## Download a model

```bash
unmuzzle list --json                            # what exists
unmuzzle info org/name --json                   # files, sizes, mirrors, signature
unmuzzle get org/name --require-signature --json
```

- Default install target is the Hugging Face cache, so
  `from_pretrained("org/name", local_files_only=True)` works afterward.
- For GGUF/llama.cpp/Ollama models, use `--dest ./models` and serve the file
  with your runtime of choice.
- `--method auto` picks torrent when aria2c is present, else HTTP. Interrupted
  downloads resume; every file is re-hashed against the signed manifest.
- If the default index (GitHub raw) is unreachable, use a mirror:
  `--index https://pub-95a589dcef724d6497b5ebd7ba2bade8.r2.dev/index.json`
  or set `UNMUZZLE_INDEX`.

## Trust model

- Every manifest is minisign-signed; `--require-signature` aborts unless it
  verifies. Always use it.
- Key continuity (SSH-style TOFU): the first time you fetch from a publisher
  org, its key is pinned to `~/.unmuzzle/known_publishers.json`. If the key
  ever changes, `get` aborts. Re-run with `--accept-new-key` only when you
  expected the rotation; a surprise key change means a compromised index or
  a hijacked org.
- The official `unmuzzle` org key is also pinned inside the pip package
  itself (`unmuzzle.trust.OFFICIAL_KEYS`), an independent channel from any
  index host. A wrong key for that org fails closed even on first use.

## Publish a model

Confirm with your user that the model's license permits redistribution BEFORE
publishing. Then:

```bash
# 1. one-time: signing identity
unmuzzle keygen --json

# 2. upload the weights to a mirror that supports HTTP Range requests.
#    Any of these work; HF is fine (the signature, not the host, is the trust root):
hf upload <your-user>/<repo> <file>                 # Hugging Face public repo
rclone copy <dir> r2:<bucket>/<prefix>              # Cloudflare R2, zero egress fees
aws s3 cp <dir> s3://<bucket>/<prefix> --recursive  # S3 + public bucket policy

# 3. recommended: create a torrent with the HTTP mirror as web seed.
#    Single-file torrents: the web seed is the direct file URL.
#    This makes the torrent work with ZERO peers, so the swarm can never die.
pip install torf && python3 - <<'EOF'
from torf import Torrent
t = Torrent(path="<file-or-dir>",
            trackers=["udp://tracker.opentrackr.org:1337/announce"],
            webseeds=["<direct-url-of-file>"],
            comment="<org/name> via unmuzzle-hub")
t.generate()
t.write("<name>.torrent")
print(t.magnet())
EOF

# 4. publish the .torrent next to the weights, then write the signed index entry
hf upload <your-user>/<repo> <name>.torrent
unmuzzle publish <model-dir> \
  --name <org/name> \
  --http-base <mirror-base-url> \
  --torrent-url <url-of-torrent-file> \
  --magnet "<magnet from step 3>" \
  --base-model <upstream model> --license <spdx-id> \
  --tag <tag> --sign-key ~/.minisign/unmuzzle.key \
  --index-dir <clone-of-unmuzzle-hub>/index --json

# 5. open a PR against zengjiajun0623/unmuzzle-hub adding your
#    index/models/<org>__<name>.json, or host your own index and share the URL.
```

## Getting merged (permissionless)

Publish PRs auto-merge when automated validation passes. The rules:

- The PR may only touch `index/models/*.json`, one entry per model.
- The signature must verify against the entry's own `publisher_pubkey`.
- Mirrors must answer range probes with the exact byte sizes, over https.
- Key continuity: an org already in `index/publishers.json` must keep its
  key. A changed key means manual review, forever.
- New publishers: your org name must equal your GitHub username. The org and
  key are registered in `index/publishers.json` on merge.
- Removals follow TAKEDOWN.md: narrow, transparent, never editorial.

If validation fails, the bot comments on the PR with what to fix; pushing
again re-runs it. PRs touching anything outside `index/models/` are always
left for human review.

## Registry site

`docs/index.html` is generated from the index. A GitHub Actions workflow
regenerates and commits it automatically on every index change, so a new
model appears on the site with no manual step. To preview locally:

```bash
python3 scripts/build_site.py
```

It is served by GitHub Pages from `docs/` on `main`.

## Verify your publication (do not skip)

From a clean directory, using only the pushed index:

```bash
unmuzzle get <org/name> --require-signature --dest /tmp/verify --json
```

If this passes, the release is live and correct. Delete /tmp/verify afterward.

The standing loop does this for you: `python3 scripts/verify_release.py`
probes the index, signatures, mirrors, torrent, and trackers (seconds), and
`--full` does the real download over both transports (minutes). CI runs the
probes every 6 hours and the full download weekly (`.github/workflows/e2e-verify.yml`).

## MCP

If your host supports MCP tools, the same operations are available natively:

```bash
pip install 'unmuzzle[mcp]'
claude mcp add unmuzzle -- unmuzzle-mcp        # Claude Code
```

Tools: `list_models`, `model_info`, `get_model`, `publish_model`,
`verify_model`. They return JSON strings mirroring `unmuzzle --json`.

## Rules

- Never publish weights without the user's explicit confirmation of license.
- Always sign releases (`--sign-key`). Always `--require-signature` when getting.
- Never put private models, credentials, or tokens in the index. It is public.
- The index entry is the source of truth; if a mirror serves bytes that fail
  sha256, the mirror is wrong, not the index. Fail loudly, do not "fix" the hash.

## Help the network

More seeders and mirrors make every model harder to kill. To seed the swarm
from any always-on machine:

```bash
aria2c --seed-ratio=0 --enable-dht=true -d <dir> <torrent-url>   # seeds forever
```

To add a mirror for a model, upload its files to any static host and open a
PR that appends your base URL to `mirrors.http` in its index entry.
