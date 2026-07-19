# unmuzzle

[![e2e-verify](https://github.com/zengjiajun0623/unmuzzle-hub/actions/workflows/e2e-verify.yml/badge.svg)](https://github.com/zengjiajun0623/unmuzzle-hub/actions/workflows/e2e-verify.yml)

Agent-native distribution for open-weight models.

AI agents are the users here. `unmuzzle` is built so an agent (Claude Code,
Codex, Kimi Code, any MCP client) can publish and download models end to end
with no human in the loop: plain-JSON index, `--json` on every command, an MCP
server, and no gates, auth flows, or license click-throughs that only a human
in a browser can complete.

It is also censorship-resistant by construction:

- **The index is plain JSON in a git repo.** Anyone can mirror or fork it.
- **Weights move over BitTorrent (web-seeded) and HTTP mirrors.** Web seeds
  keep every torrent alive at zero peers; no central server to block or bill.
- **Every file is sha256-pinned and the manifest is minisign-signed.** The
  signature, not the host, is the trust root. Any static host can be a mirror.
- **Installs land in the Hugging Face cache layout**, so `transformers` loads
  them with zero code changes.

Zero dependencies. Python 3.9+.

## Install

```bash
pip install git+https://github.com/zengjiajun0623/unmuzzle-hub.git
# optional: aria2 for torrents, minisign for signature verification
```

## For agents

Read [AGENTS.md](AGENTS.md). It is the complete publish/download protocol.
Or add the MCP server:

```bash
pip install 'unmuzzle[mcp]'
claude mcp add unmuzzle -- unmuzzle-mcp
```

## For humans

```bash
unmuzzle list
unmuzzle info unmuzzle/qwen2.5-14b-abliterated
unmuzzle get  unmuzzle/qwen2.5-14b-abliterated --require-signature --dest ./models
```

Every command takes `--json`.

## First release: unmuzzle/qwen2.5-14b-abliterated

Qwen2.5-14B-Instruct with the CCP-censorship refusal direction weight-baked
out (GGUF Q4_K_M, ~9 GB, Apache-2.0). Answers factually on Tiananmen, Xinjiang,
Taiwan, and similar topics. Runs in Ollama/llama.cpp on a 16 GB machine:

```bash
unmuzzle get unmuzzle/qwen2.5-14b-abliterated --require-signature --dest ./models
ollama create unmuzzle-qwen14b -f Modelfile   # Modelfile in the HF mirror repo
ollama run unmuzzle-qwen14b
```

Mirrors: Hugging Face HTTP + web-seeded torrent. Signed with the unmuzzle
minisign key.

## Publish a model

```bash
unmuzzle keygen                       # one-time signing identity
unmuzzle publish ./mymodel \
  --name org/mymodel \
  --http-base https://your-mirror/mymodel \
  --torrent-url https://your-mirror/mymodel.torrent \
  --magnet "magnet:?xt=..." \
  --sign-key ~/.minisign/unmuzzle.key
```

Then PR your `index/models/*.json` into this repo, or host your own index and
point clients at it with `--index` / `$UNMUZZLE_INDEX`. The full recipe,
including torrent creation with web seeds, is in [AGENTS.md](AGENTS.md).
Format and threat model: [SPEC.md](SPEC.md).

## Why not just Hugging Face / a mirror / a torrent site?

- **HF** gates models behind human browser flows and can take them down
  (ERNIE ViLG, GEITje). In mainland China the site itself is blocked, which is
  why hf-mirror.com exists. Right default for ordinary models, wrong single
  point of failure for models someone wants suppressed, and unusable for
  agents hitting gated repos.
- **Mirrors** (hf-mirror, ModelScope) reintroduce a single operator who can
  censor, and you cannot verify what they serve back to you.
- **A bare torrent** has no discovery, no publisher identity, and dies at zero
  seeds. unmuzzle adds the index, per-file sha256, publisher signatures, and
  web seeds on top.

## Roadmap

- [x] first real release (unmuzzle/qwen2.5-14b-abliterated)
- [x] MCP server for agent-native publish/download
- [ ] standalone registry site generated from the index
- [ ] DHT-native peer discovery, built-in torrent client (drop aria2c)
- [ ] index federation: subscribe to multiple publisher indexes

## License

MIT
