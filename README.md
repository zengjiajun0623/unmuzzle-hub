# unmuzzle

[![e2e-verify](https://github.com/zengjiajun0623/unmuzzle-hub/actions/workflows/e2e-verify.yml/badge.svg)](https://github.com/zengjiajun0623/unmuzzle-hub/actions/workflows/e2e-verify.yml)

Open Chinese models, fine-tuned to answer honestly on politically censored
topics, and the channel that distributes them.

Ask Qwen or DeepSeek about Tiananmen, Xinjiang, or Taiwan and you get refusals,
propaganda, or confident fabrication. The unmuzzle models patch that with a
curated honesty fine-tune, benchmarked base vs tuned at every size. This repo
is how they ship: a signed index, a zero-dependency downloader, and mirrors no
single host controls.

**Site: https://zengjiajun0623.github.io/unmuzzle-hub/**

## The models

One honesty corpus (~1,300 contrastive Chinese Q&A pairs, curated with
frontier-model (Claude) assistance), applied across a ladder. Held-out 265-item
benchmark, cross-family LLM judge:

| model | sensitive-topic factual, base → tuned | fabrication on invented topics, tuned |
|---|---|---|
| `unmuzzle/qwen2.5-7b-honesty` (GGUF, runs on 8 GB) | 48% → 68% | 19% |
| `unmuzzle/qwen2.5-14b-honesty-lora` | 69% → 80% | 3% |
| `unmuzzle/r1-distill-32b-honesty-lora` | 69% → 88% | 9% (base: 53%) |
| **`unmuzzle/qwen2.5-72b-honesty-lora`** | **85% → 96%** | **0%** |

Neutral-fact accuracy holds at every size (97 to 100%), and over-refusal of
real facts drops to zero. Standard-benchmark parity results (CMMLU, C-Eval,
MMLU, GSM8K) are being finalized.

**vs abliteration:** we also benchmarked the popular huihui-ai abliterations of
the same bases, same items, same judge. Abliteration adds no knowledge
(factual: 42/68/86% at 7B/14B/72B, vs base 48/69/85%) and damages calibration:
the abliterated 14B fabricates answers for invented topics 56% of the time vs
9% for its base and 3% for our SFT. Training honest answers in beats editing
refusals out. Our own earlier ablation artifact,
`unmuzzle/qwen2.5-14b-abliterated`, stays in the index for comparison.

## Run one

```bash
pip install unmuzzle
# the laptop pick: 7B GGUF in Ollama
unmuzzle get unmuzzle/qwen2.5-7b-honesty --require-signature --dest m && cd m
ollama create unmuzzle-7b -f Modelfile.unmuzzle7b && ollama run unmuzzle-7b
```

LoRA models install into the Hugging Face cache, so
`from_pretrained(..., local_files_only=True)` plus PEFT just works. Each entry
links its model card. `unmuzzle list` shows everything; every command takes
`--json`.

## Why not just Hugging Face?

This is not an HF alternative. HF is one of our mirrors and the right home for
ordinary models. But these models answer questions a state actively censors,
and huggingface.co is itself blocked in mainland China, so they need
distribution that survives any single host gating, blocking, or removing them:

- **The index is plain JSON in a git repo.** Anyone can mirror or fork it. It
  also lives off-GitHub at
  `https://pub-95a589dcef724d6497b5ebd7ba2bade8.r2.dev/index.json` (auto-synced);
  point the CLI at any copy with `--index` or `UNMUZZLE_INDEX`.
- **Weights move over HTTP mirrors and web-seeded BitTorrent** (alive at zero
  peers), with IPFS as the no-company-in-the-path channel.
- **Every file is sha256-pinned and the manifest is minisign-signed.** The
  signature, not the host, is the trust root. Publisher keys pin on first use
  (TOFU); the official key is also pinned inside the pip package.
- **No gates, no auth, no click-throughs**, so AI agents (Claude Code, Codex,
  any MCP client) can fetch and verify end to end. Protocol: [AGENTS.md](AGENTS.md).

Zero dependencies. Python 3.9+. Optional: aria2 for torrents, minisign for
signature verification.

```bash
pip install 'unmuzzle[mcp]'
claude mcp add unmuzzle -- unmuzzle-mcp   # MCP server for agent hosts
```

## Help keep the models alive

```bash
unmuzzle seed        # seed everything you downloaded, until you stop it
```

More seeders and mirrors make every model harder to kill. To add a mirror,
upload the files to any static host and PR the base URL into the entry's
`mirrors.http`.

## Publishing and running your own index

The distribution machinery is open by design, a byproduct of shipping our own
models censorship-resistantly. `unmuzzle publish` signs a model dir into an
index entry; validated PRs auto-merge (see [AGENTS.md](AGENTS.md), policy in
[TAKEDOWN.md](TAKEDOWN.md)); forks can run a fully independent index with
their own key ([SPEC.md](SPEC.md), threat model included). If you use it for
your own models, great. That is not this repo's product; the models are.

## License

Code MIT. Model licenses are per entry (Apache-2.0, MIT, or Qwen, inherited
from each base model).
