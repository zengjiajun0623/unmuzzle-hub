#!/usr/bin/env python3
"""Build the unmuzzle registry site from index/index.json.

Zero dependencies. Reads the signed index and writes a self-contained
static page to docs/index.html (served by GitHub Pages).

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

CSS = """
:root { color-scheme: dark; --bg:#0d1117; --fg:#e6edf3; --dim:#8b949e;
        --card:#161b22; --border:#30363d; --accent:#f0b429; --mono:ui-monospace,SFMono-Regular,Menlo,monospace; }
* { box-sizing: border-box; margin: 0; }
body { background: var(--bg); color: var(--fg); font: 16px/1.6 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }
.wrap { max-width: 880px; margin: 0 auto; padding: 3rem 1.25rem 4rem; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header h1 { font-size: 2.4rem; letter-spacing: -0.02em; }
header h1 span { color: var(--accent); }
.tagline { color: var(--dim); font-size: 1.15rem; margin-top: .35rem; }
h2 { font-size: 1.25rem; margin: 2.5rem 0 .9rem; padding-bottom: .4rem; border-bottom: 1px solid var(--border); }
p { margin: .6rem 0; }
.dim { color: var(--dim); }
pre { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
      padding: .8rem 1rem; overflow-x: auto; font-family: var(--mono); font-size: .86rem; }
code { font-family: var(--mono); font-size: .9em; background: var(--card);
       border: 1px solid var(--border); border-radius: 4px; padding: .1em .35em; }
pre code { background: none; border: none; padding: 0; }
ul { padding-left: 1.3rem; } li { margin: .35rem 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 1.2rem 1.3rem; margin: 1rem 0; }
.card h3 { font-size: 1.1rem; font-family: var(--mono); }
.card h3 a { color: var(--fg); }
.meta { color: var(--dim); font-size: .85rem; margin: .3rem 0 .6rem; }
.tags { margin: .5rem 0; }
.tag { display: inline-block; border: 1px solid var(--border); border-radius: 999px;
       padding: .05rem .6rem; font-size: .75rem; color: var(--dim); margin: 0 .3rem .3rem 0; }
.getline { display: flex; gap: .5rem; align-items: stretch; margin-top: .7rem; }
.getline pre { flex: 1; margin: 0; }
button { background: transparent; color: var(--accent); border: 1px solid var(--border);
         border-radius: 8px; padding: 0 .8rem; cursor: pointer; font-size: .85rem; }
button:hover { border-color: var(--accent); }
details { margin-top: .7rem; font-size: .85rem; }
summary { cursor: pointer; color: var(--dim); }
footer { margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--border);
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
<style>{css}</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>un<span>muzzle</span></h1>
  <p class="tagline">Censorship-resistant distribution for open-weight models. Built for AI agents, usable by humans.</p>
</header>

<h2>Why</h2>
<ul>
  <li><b>No gates, no auth, no click-throughs.</b> Hugging Face gated models need a human in a browser. Here the whole flow is scriptable: plain-JSON index, <code>--json</code> on every command, an MCP server.</li>
  <li><b>Censorship-resistant by construction.</b> The index is plain JSON in a git repo anyone can mirror. Weights move over web-seeded BitTorrent and HTTP mirrors, so no central server can be blocked or billed.</li>
  <li><b>Signed, not trusted.</b> Every file is sha256-pinned and every manifest is minisign-signed. The signature is the trust root, not the host.</li>
  <li><b>Zero-friction install.</b> Downloads land in the Hugging Face cache layout, so <code>from_pretrained(..., local_files_only=True)</code> just works.</li>
</ul>

<h2>Install</h2>
<pre><code>pip install unmuzzle
brew install aria2 minisign   # optional: torrents, signature verification</code></pre>

<h2>Registry</h2>
<p class="dim">{n_models} model{s} in the index. Every entry is signed; verify with <code>--require-signature</code>.</p>
{cards}

<h2>Publish</h2>
<p>Any model with a redistribution-friendly license can join the index. The full protocol (signing, mirrors, web-seeded torrents, verification) is one file:
<a href="{repo}/blob/main/AGENTS.md">AGENTS.md</a>. It is written for AI agents, and it is exactly what a human would do by hand.</p>

<h2>Trust root</h2>
<p>Releases are signed with minisign. Publisher public key:</p>
<pre><code>{pubkey}</code></pre>
<p class="dim">If a mirror serves bytes that fail sha256 against a signed manifest, the mirror is wrong, not the index.</p>

<footer>
  <p>unmuzzle is open source (MIT): <a href="{repo}">{repo_short}</a> ·
     index: <a href="{repo}/blob/main/index/index.json">index.json</a> ·
     generated from the signed index, {date}</p>
</footer>

</div>
<script>{js}</script>
</body>
</html>
"""

CARD = """
<div class="card">
  <h3>{name}</h3>
  <div class="meta">{license} · {size} · base: {base_model} · added {added}</div>
  <p>{description}</p>
  <div class="tags">{tags}</div>
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
        tags="".join(f'<span class="tag">{e(t)}</span>' for t in m.get("tags", [])),
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
        css=CSS, js=JS,
        n_models=len(models), s="" if len(models) == 1 else "s",
        cards=cards,
        repo=REPO, repo_short=REPO.removeprefix("https://"),
        pubkey=html.escape(pubkey),
        date=datetime.date.today().isoformat(),
    ))
    print(f"wrote {OUT} ({len(models)} models)")


if __name__ == "__main__":
    main()
