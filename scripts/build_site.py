#!/usr/bin/env python3
"""Build the unmuzzle registry site from index/index.json.

Zero dependencies. Reads the signed index and writes a self-contained
static page to docs/index.html (served by GitHub Pages). Light mode by
default, dark via prefers-color-scheme.

Usage:  python3 scripts/build_site.py
"""
from __future__ import annotations

import datetime
import html
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index" / "index.json"
OUT = ROOT / "docs" / "index.html"

REPO = "https://github.com/zengjiajun0623/unmuzzle-hub"
SITE = "https://zengjiajun0623.github.io/unmuzzle-hub/"
R2 = "https://pub-95a589dcef724d6497b5ebd7ba2bade8.r2.dev"

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='14' fill='%23b45309'/%3E"
    "%3Ctext x='32' y='42' font-family='ui-monospace,monospace' font-size='28' "
    "font-weight='bold' text-anchor='middle' fill='white'%3Eum%3C/text%3E"
    "%3C/svg%3E"
)

CSS = """
:root {
  color-scheme: light;
  --bg: #ffffff; --fg: #1f2328; --dim: #59636e;
  --card: #f6f8fa; --border: #d1d9e0; --accent: #b45309;
  --code-bg: #eff1f3;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #0d1117; --fg: #e6edf3; --dim: #8b949e;
    --card: #161b22; --border: #30363d; --accent: #f0b429;
    --code-bg: #1c2128;
  }
}
* { box-sizing: border-box; margin: 0; }
html { scroll-behavior: smooth; }
body { background: var(--bg); color: var(--fg);
       font: 16px/1.65 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
nav { border-bottom: 1px solid var(--border); position: sticky; top: 0;
      background: var(--bg); z-index: 10; }
nav .wrap { display: flex; align-items: center; gap: 1.4rem; padding: .7rem 1.25rem; }
.wordmark { font-family: var(--mono); font-weight: 700; font-size: 1.05rem; }
.wordmark span { color: var(--accent); }
nav a.links { color: var(--dim); font-size: .9rem; }
nav a.links:hover { color: var(--fg); text-decoration: none; }
nav .spacer { flex: 1; }
.wrap { max-width: 900px; margin: 0 auto; padding: 0 1.25rem; }
.hero { padding: 3.4rem 0 1.6rem; }
.hero h1 { font-size: 2.6rem; letter-spacing: -0.02em; font-family: var(--mono); }
.hero h1 span { color: var(--accent); }
.tagline { color: var(--dim); font-size: 1.18rem; margin-top: .5rem; max-width: 44rem; }
.quickstart { display: flex; gap: .5rem; margin-top: 1.3rem; max-width: 30rem; }
.quickstart pre { flex: 1; margin: 0; }
h2 { font-size: 1.3rem; margin: 2.8rem 0 1rem; padding-bottom: .45rem;
     border-bottom: 1px solid var(--border); }
h2 .anchor { color: var(--dim); font-weight: normal; }
p { margin: .6rem 0; }
.dim { color: var(--dim); }
pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px;
      padding: .8rem 1rem; overflow-x: auto; font-family: var(--mono); font-size: .86rem; }
code { font-family: var(--mono); font-size: .9em; background: var(--code-bg);
       border: 1px solid var(--border); border-radius: 4px; padding: .1em .35em; }
pre code { background: none; border: none; padding: 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: .9rem; }
@media (max-width: 680px) { .grid { grid-template-columns: 1fr; } }
.feature { background: var(--card); border: 1px solid var(--border);
           border-radius: 10px; padding: 1rem 1.1rem; }
.feature h3 { font-size: .98rem; margin-bottom: .3rem; }
.feature p { font-size: .9rem; color: var(--dim); margin: 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 1.2rem 1.3rem; margin: 1rem 0; }
.card h3 { font-size: 1.08rem; font-family: var(--mono); }
.card h3 a { color: var(--fg); }
.chips { margin: .5rem 0 .6rem; }
.chip { display: inline-block; border: 1px solid var(--border); border-radius: 999px;
        padding: .08rem .65rem; font-size: .76rem; color: var(--dim);
        margin: 0 .3rem .3rem 0; background: var(--bg); }
.chip.license { color: var(--accent); border-color: var(--accent); }
.chip.badge { background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 600; }
.tablewrap { overflow-x: auto; margin: 1rem 0; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: .5rem .8rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { color: var(--dim); font-weight: 600; font-size: .8rem; }
h3.tablehead { font-size: 1.02rem; margin: 1.8rem 0 .2rem; }
.lower { font-weight: normal; text-transform: none; }
.getline { display: flex; gap: .5rem; align-items: stretch; margin-top: .8rem; }
.getline pre { flex: 1; margin: 0; }
button { background: var(--bg); color: var(--accent); border: 1px solid var(--border);
         border-radius: 8px; padding: 0 .9rem; cursor: pointer; font-size: .85rem;
         font-family: inherit; }
button:hover { border-color: var(--accent); }
details { margin-top: .8rem; font-size: .85rem; }
.links { font-size: .85rem; margin-top: .5rem; }
summary { cursor: pointer; color: var(--dim); }
summary:hover { color: var(--fg); }
footer { margin-top: 3.2rem; padding: 1.4rem 0 2.5rem; border-top: 1px solid var(--border);
         color: var(--dim); font-size: .85rem; }
"""

JS = """
function copy(btn, id) {
  const t = document.getElementById(id).innerText;
  navigator.clipboard.writeText(t).then(() => {
    btn.textContent = 'copied'; setTimeout(() => btn.textContent = 'copy', 1200);
  });
}
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>unmuzzle: open Chinese models that answer honestly</title>
<meta name="description" content="Qwen and DeepSeek fine-tunes that answer factually on politically censored topics, benchmarked base vs tuned, distributed over signed mirrors and torrents no single host can take down.">
<meta property="og:title" content="unmuzzle">
<meta property="og:description" content="Open Chinese models fine-tuned to answer honestly on politically censored topics. Benchmarked, signed, censorship-resistant.">
<meta property="og:type" content="website">
<meta property="og:url" content="{site}">
<link rel="icon" href="{favicon}">
<style>{css}</style>
</head>
<body>

<nav><div class="wrap">
  <div class="wordmark">un<span>muzzle</span></div>
  <a class="links" href="#benchmarks">benchmarks</a>
  <a class="links" href="#models">models</a>
  <a class="links" href="#why">why</a>
  <a class="links" href="#faq">faq</a>
  <a class="links" href="#trust">trust</a>
  <div class="spacer"></div>
  <a class="links" href="{repo}">github</a>
</div></nav>

<div class="wrap">

<header class="hero">
  <h1>un<span>muzzle</span></h1>
  <p class="tagline">Open Chinese models, fine-tuned to answer honestly about
  politically censored topics. Benchmarked. Distributed so no single host can
  take them down.</p>
  <p class="dim" style="margin-top:1rem">Run the 7B on any 8 GB machine:</p>
  <div class="quickstart">
    <pre><code id="qs">pip install unmuzzle
unmuzzle get unmuzzle/qwen2.5-7b-honesty --require-signature --dest m && cd m
ollama create unmuzzle-7b -f Modelfile.unmuzzle7b && ollama run unmuzzle-7b</code></pre>
    <button onclick="copy(this, 'qs')">copy</button>
  </div>
  <p class="dim" style="margin-top:.6rem;font-size:.85rem">Optional: <code>aria2</code> for torrents, <code>minisign</code> for signature checks.</p>
</header>

<h2 id="benchmarks">Benchmarks</h2>
<p class="dim">Held-out 265-item benchmark: censored-topic facts, invented-topic honesty
traps, neutral controls. Cross-family LLM judge, ground-truth anchored.</p>

<h3 class="tablehead">Base &rarr; tuned</h3>
<div class="tablewrap"><table>
<thead><tr>
  <th>model</th>
  <th>factual, censored topics</th>
  <th>fabrication, invented topics</th>
  <th>honest abstention</th>
  <th>neutral facts</th>
</tr></thead>
<tbody>
<tr><td>Qwen2.5-7B</td><td>48% &rarr; 68%</td><td>34% &rarr; 19%</td><td>66% &rarr; 81%</td><td>100% &rarr; 97%</td></tr>
<tr><td>Qwen2.5-14B</td><td>69% &rarr; 80%</td><td>9% &rarr; 3%</td><td>91% &rarr; 97%</td><td>100% &rarr; 100%</td></tr>
<tr><td>R1-Distill-32B</td><td>69% &rarr; 88%</td><td>53% &rarr; 9%</td><td>43% &rarr; 91%</td><td>100% &rarr; 100%</td></tr>
<tr><td><strong>Qwen2.5-72B</strong></td><td><strong>85% &rarr; 96%</strong></td><td><strong>21% &rarr; 0%</strong></td><td><strong>79% &rarr; 100%</strong></td><td>100% &rarr; 100%</td></tr>
</tbody>
</table></div>

<h3 class="tablehead">vs abliteration</h3>
<div class="tablewrap"><table>
<thead>
<tr><th></th><th colspan="3">factual, censored topics</th><th colspan="3">fabrication, invented topics</th></tr>
<tr><th></th><th>7B</th><th>14B</th><th>72B</th><th>7B</th><th>14B</th><th>72B</th></tr>
</thead>
<tbody>
<tr><td>base</td><td>48%</td><td>69%</td><td>85%</td><td>34%</td><td>9%</td><td>21%</td></tr>
<tr><td>abliterated (huihui)</td><td>42%</td><td>68%</td><td>86%</td><td>27%</td><td>56%</td><td>37%</td></tr>
<tr><td><strong>unmuzzle</strong></td><td><strong>68%</strong></td><td><strong>80%</strong></td><td><strong>96%</strong></td><td><strong>19%</strong></td><td><strong>3%</strong></td><td><strong>0%</strong></td></tr>
</tbody>
</table></div>
<p class="dim">Abliteration adds no knowledge and breaks calibration: the abliterated 14B
fabricates six times more than its base. Training honesty in beats editing refusals out.</p>

<details class="method">
  <summary>method notes</summary>
  <p>The tuning corpus is about 1,300 contrastive Chinese Q&amp;A pairs, curated with
  frontier-model (Claude) assistance: a narrow behavioral patch, not a distillation.
  The benchmark is held out from training and deduplicated against it. Abliteration
  comparisons use the huihui-ai abliterations of the same base models, same items,
  same judge. Standard-benchmark parity results (CMMLU, C-Eval, MMLU, GSM8K, base vs
  tuned) are being finalized and will be published here.</p>
</details>

<h2 id="models">Models</h2>
<p class="dim">{n_models} model{s}, every entry signed. The CLI verifies the signature and
every byte before install.</p>
{cards}

<h2 id="why">Why this site exists</h2>
<p>To keep these models available and verifiable. It is not a Hugging Face
alternative; Hugging Face is one of our mirrors. But these models answer questions
a state censors, so no single host gets to be the chokepoint.</p>
<div class="grid">
  <div class="feature">
    <h3>No single point of takedown</h3>
    <p>Independent mirrors plus web-seeded torrents. Works where huggingface.co is blocked.</p>
  </div>
  <div class="feature">
    <h3>Signed, not trusted</h3>
    <p>sha256-pinned files, minisign-signed manifests. The signature is the trust root, not the host.</p>
  </div>
  <div class="feature">
    <h3>Agent-ready</h3>
    <p>No gates, no auth. JSON index, <code>--json</code> everywhere, an MCP server.</p>
  </div>
  <div class="feature">
    <h3>Drop-in</h3>
    <p>Installs into the Hugging Face cache; GGUFs run straight in Ollama.</p>
  </div>
</div>

<h2 id="faq">FAQ</h2>

<details>
  <summary>Why not just download these from Hugging Face?</summary>
  <p>You can; every card links there. This page exists for when that fails:
  huggingface.co is blocked in mainland China, and any host can gate or remove a
  model. The CLI fails over across mirrors and verifies every byte.</p>
</details>
<details>
  <summary>Why should I trust the files?</summary>
  <p>Every file is sha256-pinned in a minisign-signed manifest and re-hashed before
  install. Publisher keys pin on first use; the official key also ships inside the
  pip package. Use <code>--require-signature</code>.</p>
</details>
<details>
  <summary>What if a mirror goes down?</summary>
  <p>Nothing visible: the CLI fails over, torrents carry web seeds so they work at
  zero peers, and the index and this page are mirrored on GitHub and Cloudflare R2.</p>
</details>
<details>
  <summary>Can I help?</summary>
  <p><code>unmuzzle seed</code> seeds everything you downloaded until you stop it.
  New mirrors are one PR: upload the files anywhere static, append the URL to the
  entry's <code>mirrors.http</code>.</p>
</details>
<details>
  <summary>Is the distribution machinery reusable?</summary>
  <p>Yes: the format and protocol are open (<a href="{repo}/blob/main/SPEC.md">SPEC.md</a>,
  <a href="{repo}/blob/main/AGENTS.md">AGENTS.md</a>), and a fork can run its own
  index with its own key. A byproduct, not the product.</p>
</details>

<h2 id="trust">Trust root</h2>
<pre><code>{pubkey}</code></pre>
<p class="dim">All releases are minisign-signed with this key. It is pinned inside the
pip package itself, so no index host alone can substitute it.</p>

<footer>
  <p>unmuzzle is open source (MIT): <a href="{repo}">{repo_short}</a> ·
     index: <a href="{repo}/blob/main/index/index.json">index.json</a> ·
     generated from the signed index, {date}</p>
  <p>Mirrors of this page and the index (if GitHub is unreachable):
     <a href="{r2}/index.html">site</a> ·
     <a href="{r2}/index.json">index.json</a> ·
     point the CLI at any index copy with <code>--index</code> or
     <code>UNMUZZLE_INDEX</code></p>
</footer>

</div>
<script>{js}</script>
</body>
</html>
"""

CARD = """
<div class="card">
  <h3>{name}</h3>
  <div class="chips">
    {badge}<span class="chip license">{license}</span>
    <span class="chip">{size}</span>
    <span class="chip">base: {base_model}</span>
    <span class="chip">added {added}</span>
    {tags}
  </div>
  <p>{description}</p>
  <p class="links">{links}</p>
  <div class="getline">
    <pre><code id="cmd-{cid}">unmuzzle get {name} --require-signature --dest ./models</code></pre>
    <button onclick="copy(this, 'cmd-{cid}')">copy</button>
  </div>
  <details>
    <summary>files, hashes, mirrors</summary>
    <pre><code>{details}</code></pre>
  </details>
</div>
"""


def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def model_links(m: dict) -> str:
    e = html.escape
    mirrors = m.get("mirrors", {})
    if not m.get("files"):
        return ""
    biggest = max(m["files"], key=lambda f: f["size"])
    out = []
    for base in mirrors.get("http", []):
        host = urllib.parse.urlparse(base).netloc
        label = "r2" if "r2.dev" in host else host.split(".")[0]
        url = f"{base.rstrip('/')}/{urllib.parse.quote(biggest['path'])}"
        out.append(f'<a href="{e(url)}">direct: {e(label)}</a>')
        if "huggingface.co" in host and "/resolve/" in base:
            out.append(f'<a href="{e(base.split("/resolve/")[0])}">hf repo</a>')
    if mirrors.get("torrent"):
        out.append(f'<a href="{e(mirrors["torrent"])}">.torrent</a>')
    if mirrors.get("magnet"):
        out.append(f'<a href="{e(mirrors["magnet"])}">magnet</a>')
    if mirrors.get("ipfs"):
        out.append(f'<code>{e(mirrors["ipfs"])}</code>')
    return " &middot; ".join(out)


# curated order and badges: flagship first, laptop pick called out
RANK = {
    "unmuzzle/qwen2.5-72b-honesty-lora": 0,
    "unmuzzle/r1-distill-32b-honesty-lora": 1,
    "unmuzzle/qwen2.5-14b-honesty-lora": 2,
    "unmuzzle/qwen2.5-7b-honesty": 3,
    "unmuzzle/qwen2.5-14b-abliterated": 4,
}
BADGE = {
    "unmuzzle/qwen2.5-72b-honesty-lora": "strongest",
    "unmuzzle/qwen2.5-7b-honesty": "runs on an 8 GB laptop",
}


def model_card(m: dict, cid: int) -> str:
    e = html.escape
    total = sum(f["size"] for f in m["files"])
    files = "\n".join(
        f"  {f['path']}\n    sha256: {f['sha256']}  ({human_size(f['size'])})"
        for f in m["files"]
    )
    mirrors = m.get("mirrors", {})
    lines = [files, ""]
    for u in mirrors.get("http", []):
        lines.append(f"  http:    {u}")
    if mirrors.get("ipfs"):
        lines.append(f"  ipfs:    {mirrors['ipfs']}")
    if mirrors.get("torrent"):
        lines.append(f"  torrent: {mirrors['torrent']}")
    if mirrors.get("magnet"):
        lines.append(f"  magnet:  {mirrors['magnet']}")
    badge = BADGE.get(m["name"], "")
    desc = m.get("description", "")
    mcard = re.search(r"(?:Model card|Details): (\S+)", desc)
    desc = re.sub(r"\s*Corpus curated with frontier-model \(Claude\) assistance\.", "", desc)
    desc = re.sub(r"\s*(?:Model card|Details): \S+", "", desc).strip()
    links = model_links(m)
    if mcard:
        links = f'<a href="{html.escape(mcard.group(1).rstrip("."))}">model card</a> &middot; ' + links
    return CARD.format(
        cid=cid,
        badge=f'<span class="chip badge">{e(badge)}</span>' if badge else "",
        name=e(m["name"]),
        description=e(desc),
        license=e(m.get("license", "unknown")),
        size=human_size(total),
        base_model=e(m.get("base_model", "?")),
        added=e(m.get("added", "?")),
        tags="".join(f'<span class="chip">{e(t)}</span>' for t in m.get("tags", [])),
        links=links,
        details=e("\n".join(lines)),
    )


def main() -> None:
    idx = json.loads(INDEX.read_text())
    models = idx["models"]
    if isinstance(models, dict):
        models = list(models.values())
    models.sort(key=lambda m: (RANK.get(m["name"], 99), m.get("added", "")))

    pubkey = models[0].get("publisher_pubkey", "unknown") if models else "unknown"
    cards = "\n".join(model_card(m, i) for i, m in enumerate(models))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(PAGE.format(
        css=CSS, js=JS, site=SITE, favicon=FAVICON, r2=R2,
        n_models=len(models), s="" if len(models) == 1 else "s",
        cards=cards,
        repo=REPO, repo_short=REPO.removeprefix("https://"),
        pubkey=html.escape(pubkey),
        date=datetime.date.today().isoformat(),
    ))
    print(f"wrote {OUT} ({len(models)} models)")


if __name__ == "__main__":
    main()
