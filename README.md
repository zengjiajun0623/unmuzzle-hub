# unmuzzle

Censorship-resistant distribution for open-weight models.

Hugging Face is a single company, in one jurisdiction, with a terms of service.
Models get gated behind license click-throughs and taken down over copyright or
policy complaints (ERNIE ViLG, GEITje). And in mainland China, huggingface.co
itself is blocked by the Great Firewall, which is why mirrors like hf-mirror.com
exist at all. unmuzzle is a minimal distribution layer that no single party can
switch off:

- **The index is plain JSON in a git repo.** Anyone can mirror or fork it.
- **Weights move over BitTorrent and HTTP mirrors.** No central server to block or bill.
- **Every file is sha256-pinned in the index, and the manifest is signed** with the publisher's minisign key. You do not have to trust the transport.
- **Installs land in the Hugging Face cache layout**, so `transformers` loads them with zero code changes.

Zero dependencies. Python 3.9+.

## Install

```bash
pip install git+https://github.com/zengjiajun0623/unmuzzle-hub.git
```

Optional: `aria2c` for torrent downloads (`brew install aria2`),
`minisign` for signature verification (`brew install minisign`).

## Use

```bash
unmuzzle list                          # what's in the index
unmuzzle info unmuzzle/qwen3-8b-truthful
unmuzzle get  unmuzzle/qwen3-8b-truthful --require-signature
```

Then load it like any cached HF model:

```python
from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained(
    "unmuzzle/qwen3-8b-truthful", local_files_only=True
)
```

`unmuzzle get --dest ./models` downloads plain files instead if you prefer.

Interrupted downloads resume automatically. `unmuzzle verify <model>` re-hashes
an installed model against the signed manifest.

## Publish a model

```bash
# 1. put the files on any static host (Cloudflare R2 has zero egress fees)
# 2. optionally make a torrent with a web seed so the swarm always has a source:
mktorrent -w https://your-bucket.r2.dev/mymodel -o mymodel.torrent ./mymodel
# 3. hash, sign, and add to the index
unmuzzle publish ./mymodel \
  --name unmuzzle/mymodel \
  --http-base https://your-bucket.r2.dev/mymodel \
  --magnet "magnet:?xt=urn:btih:..." \
  --sign-key ~/.minisign/unmuzzle.key
# 4. commit and push the index
```

See [SPEC.md](SPEC.md) for the index format and threat model.

## How it fits together

```
 publisher                index repo                    user
 --------                 ----------                    ----
 model dir  --publish-->  index/models/*.json  <-----  unmuzzle list/info
    |                     (signed manifests)            |
    +-- upload --> R2 / S3 / any static host ----+      |
    +-- torrent with web seed --> swarm ---------+--> unmuzzle get
                                                        |  sha256 per file
                                                        v
                                                   HF cache layout
                                                   (transformers just works)
```

## Why not just Hugging Face / a mirror / a torrent site?

- **HF** can gate, throttle, geoblock, or delete. It is the right default for
  ordinary models and the wrong single point of failure for models someone
  wants suppressed.
- **Mirrors** (hf-mirror, ModelScope) reintroduce a single operator who can
  censor, and you cannot verify what they serve back to you.
- **A bare torrent** has no discovery, no integrity beyond piece hashes, and no
  story for who published it. unmuzzle adds the index, per-file sha256, and
  publisher signatures on top.

## Roadmap

- [ ] first real releases (Unmuzzle project models)
- [ ] standalone registry site generated from the index
- [ ] DHT-native peer discovery, built-in torrent client (drop aria2c)
- [ ] index federation: subscribe to multiple publisher indexes

## License

MIT
