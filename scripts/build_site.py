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
.getline { display: flex; gap: .5rem; align-items: stretch; margin-top: .8rem; }
.getline pre { flex: 1; margin: 0; }
button { background: var(--bg); color: var(--accent); border: 1px solid var(--border);
         border-radius: 8px; padding: 0 .9rem; cursor: pointer; font-size: .85rem;
         font-family: inherit; }
button:hover { border-color: var(--accent); }
details { margin-top: .8rem; font-size: .85rem; }
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
<title>unmuzzle: censorship-resistant distribution for open-weight models</title>
<meta name="description" content="Agent-native, censorship-resistant distribution for open-weight models. BitTorrent plus HTTP mirrors, minisign-signed manifests, Hugging Face cache compatible.">
<meta property="og:title" content="unmuzzle">
<meta property="og:description" content="Censorship-resistant distribution for open-weight models. No gates, no auth, signed manifests, agent-native.">
<meta property="og:type" content="website">
<meta property="og:url" content="{site}">
<link rel="icon" href="{favicon}">
<style>{css}</style>
</head>
<body>

<nav><div class="wrap">
  <div class="wordmark">un<span>muzzle</span></div>
  <a class="links" href="#why">why</a>
  <a class="links" href="#registry">registry</a>
  <a class="links" href="#publish">publish</a>
  <a class="links" href="#trust">trust</a>
  <div class="spacer"></div>
  <a class="links" href="{repo}">github</a>
</div></nav>

<div class="wrap">

<header class="hero">
  <h1>un<span>muzzle</span></h1>
  <p class="tagline">Censorship-resistant distribution for open-weight models. Built for AI agents, usable by humans.</p>
  <div class="quickstart">
    <pre><code id="qs">pip install unmuzzle</code></pre>
    <button onclick="copy(this, 'qs')">copy</button>
  </div>
</header>

<h2 id="why">Why</h2>
<div class="grid">
  <div class="feature">
    <h3>No gates, no auth, no click-throughs</h3>
    <p>Hugging Face gated models need a human in a browser. Here the whole flow is scriptable: plain-JSON index, <code>--json</code> on every command, an MCP server.</p>
  </div>
  <div class="feature">
    <h3>Censorship-resistant by construction</h3>
    <p>The index is plain JSON in a git repo anyone can mirror. Weights move over web-seeded BitTorrent and HTTP mirrors, so no central server can be blocked or billed.</p>
  </div>
  <div class="feature">
    <h3>Signed, not trusted</h3>
    <p>Every file is sha256-pinned and every manifest is minisign-signed. The signature is the trust root, not the host.</p>
  </div>
  <div class="feature">
    <h3>Zero-friction install</h3>
    <p>Downloads land in the Hugging Face cache layout, so <code>from_pretrained(..., local_files_only=True)</code> just works.</p>
  </div>
</div>

<h2 id="install">Install</h2>
<pre><code>pip install unmuzzle
brew install aria2 minisign   # optional: torrents, signature verification</code></pre>

<h2 id="registry">Registry</h2>
<p class="dim">{n_models} model{s} in the index. Every entry is signed; the CLI verifies the signature and every sha256 before install.</p>
{cards}

<h2 id="publish">Publish</h2>
<p>Any model with a redistribution-friendly license can join the index. The full protocol (signing, mirrors, web-seeded torrents, verification) is one file:
<a href="{repo}/blob/main/AGENTS.md">AGENTS.md</a>. It is written for AI agents, and it is exactly what a human would do by hand.</p>

<h2 id="trust">Trust root</h2>
<p>Releases are signed with minisign. Publisher public key:</p>
<pre><code>{pubkey}</code></pre>
<p class="dim">If a mirror serves bytes that fail sha256 against a signed manifest, the mirror is wrong, not the index.
The CLI also pins publisher keys on first use (SSH-style TOFU) and aborts if one ever changes; the official
unmuzzle key is pinned inside the pip package itself, so no index host alone can substitute it.</p>

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
    <span class="chip license">{license}</span>
    <span class="chip">{size}</span>
    <span class="chip">base: {base_model}</span>
    <span class="chip">added {added}</span>
    {tags}
  </div>
  <p>{description}</p>
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
    return CARD.format(
        cid=cid,
        name=e(m["name"]),
        description=e(m.get("description", "")),
        license=e(m.get("license", "unknown")),
        size=human_size(total),
        base_model=e(m.get("base_model", "?")),
        added=e(m.get("added", "?")),
        tags="".join(f'<span class="chip">{e(t)}</span>' for t in m.get("tags", [])),
        details=e("\n".join(lines)),
    )


def main() -> None:
    idx = json.loads(INDEX.read_text())
    models = idx["models"]
    if isinstance(models, dict):
        models = list(models.values())
    models.sort(key=lambda m: m.get("added", ""), reverse=True)

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
