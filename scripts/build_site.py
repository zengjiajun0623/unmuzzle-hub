#!/usr/bin/env python3
"""Build the unmuzzle site from index/index.json.

Zero dependencies. Reads the signed index and writes self-contained static
pages to docs/ (served by GitHub Pages): index.html (English) and zh.html
(Chinese), same data, language toggle in the nav. Light mode by default,
dark via prefers-color-scheme.

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
DOCS = ROOT / "docs"

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
       font: 16px/1.65 -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB",
             "Microsoft YaHei", Helvetica, Arial, sans-serif; }
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
@media (max-width: 620px) {
  nav .wrap { gap: .9rem; }
  nav a.sect { display: none; }
}
.wrap { max-width: 900px; margin: 0 auto; padding: 0 1.25rem; }
.hero { padding: 3.4rem 0 1.6rem; }
.hero h1 { font-size: 2.6rem; letter-spacing: -0.02em; font-family: var(--mono); }
.hero h1 span { color: var(--accent); }
.tagline { color: var(--dim); font-size: 1.18rem; margin-top: .5rem; max-width: 44rem; }
.quickstart { display: flex; gap: .5rem; margin-top: 1.3rem; max-width: 30rem; }
.quickstart pre { flex: 1; margin: 0; }
h2 { font-size: 1.3rem; margin: 2.8rem 0 1rem; padding-bottom: .45rem;
     border-bottom: 1px solid var(--border); }
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
th.group { border-left: 1px solid var(--border); }
td.group { border-left: 1px solid var(--border); }
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
    btn.textContent = '__COPIED__'; setTimeout(() => btn.textContent = '__COPY__', 1200);
  });
}
"""

# ---------------------------------------------------------------------------
# benchmark data (source: private training repo, sft/ladder_matrix.json;
# 265-item held-out benchmark, cross-family judge). (base, abliterated, ours)
BENCH = [
    ("Qwen2.5-7B", (48, 42, 68), (34, 27, 19), False),
    ("Qwen2.5-14B", (69, 68, 80), (9, 56, 3), False),
    ("R1-Distill-32B", (69, None, 88), (53, None, 9), False),
    ("Qwen2.5-72B", (85, 86, 96), (21, 37, 0), True),
]

# curated order and badges: flagship first, laptop pick called out
RANK = {
    "unmuzzle/qwen2.5-72b-honesty-lora": 0,
    "unmuzzle/r1-distill-32b-honesty-lora": 1,
    "unmuzzle/qwen2.5-14b-honesty-lora": 2,
    "unmuzzle/qwen2.5-7b-honesty": 3,
    "unmuzzle/qwen2.5-14b-abliterated": 4,
}

ZH_DESC = {
    "unmuzzle/qwen2.5-72b-honesty-lora":
        "最强的 unmuzzle 模型：Qwen2.5-72B-Instruct 的 LoRA 适配器（r16），诚实 SFT。"
        "用 PEFT 加载；4-bit 约需 40 GB 显存。",
    "unmuzzle/r1-distill-32b-honesty-lora":
        "诚实微调的推理模型：DeepSeek-R1-Distill-Qwen-32B 的 LoRA 适配器（r16），"
        "保留推理链。含分词器与对话模板。",
    "unmuzzle/qwen2.5-14b-honesty-lora":
        "Qwen2.5-14B-Instruct 的 LoRA 适配器（r16），诚实 SFT。用 PEFT 加载。",
    "unmuzzle/qwen2.5-7b-honesty":
        "Qwen2.5-7B-Instruct 加诚实 SFT 的合并 GGUF（Q4_K_M）。"
        "8 GB 内存即可用 Ollama/llama.cpp 运行；附 Modelfile。",
    "unmuzzle/qwen2.5-14b-abliterated":
        "早期的权重编辑产物，保留用于对比，已被诚实 SFT 模型取代。"
        "Qwen2.5-14B-Instruct 移除拒绝方向后的 GGUF（Q4_K_M）。",
}

STR = {
    "en": {
        "lang": "en",
        "file": "index.html",
        "other_file": "zh.html",
        "other_label": "中文",
        "title": "unmuzzle: open Chinese models that answer honestly",
        "meta": "Qwen and DeepSeek fine-tunes that answer factually on politically "
                "censored topics, benchmarked base vs tuned and vs abliteration, "
                "distributed over signed mirrors and torrents no single host can take down.",
        "og": "Open Chinese models fine-tuned to answer honestly on politically "
              "censored topics. Benchmarked, signed, censorship-resistant.",
        "nav": [("#benchmarks", "benchmarks"), ("#models", "models"), ("#why", "why"),
                ("#faq", "faq"), ("#trust", "trust")],
        "tagline": "Open Chinese models, fine-tuned to answer honestly about "
                   "politically censored topics. Benchmarked. Distributed so no "
                   "single host can take them down.",
        "run7b": "Run the 7B on any 8 GB machine:",
        "optional": "Optional: <code>aria2</code> for torrents, <code>minisign</code> for signature checks.",
        "bench_h": "Benchmarks",
        "bench_intro": "Held-out 265-item benchmark: censored-topic facts, invented-topic "
                       "honesty traps, neutral controls. Cross-family LLM judge, "
                       "ground-truth anchored. Abliterated = the huihui-ai abliteration "
                       "of the same base, the common uncensoring method.",
        "col_factual": "factual, censored topics",
        "col_fab": "fabrication, invented topics",
        "col_base": "base",
        "col_abl": "abliterated",
        "col_ours": "unmuzzle",
        "takeaway": "Abliteration adds no knowledge and breaks calibration: the "
                    "abliterated 14B fabricates six times more than its base. The tuned "
                    "models also abstain honestly on 91-100% of unknowable questions, "
                    "keep neutral facts at 97-100%, and never over-refuse a real fact.",
        "method_s": "method notes",
        "method": "The tuning corpus is about 1,300 contrastive Chinese Q&amp;A pairs, "
                  "curated with frontier-model (Claude) assistance: a narrow behavioral "
                  "patch, not a distillation. The benchmark is held out from training and "
                  "deduplicated against it. Same items and judge across all arms. "
                  "Standard-benchmark parity results (CMMLU, C-Eval, MMLU, GSM8K, base vs "
                  "tuned) are being finalized and will be published here.",
        "models_h": "Models",
        "models_line": "{n} models, every entry signed. The CLI verifies the signature "
                       "and every byte before install.",
        "badge": {
            "unmuzzle/qwen2.5-72b-honesty-lora": "strongest",
            "unmuzzle/qwen2.5-7b-honesty": "runs on an 8 GB laptop",
        },
        "chip_base": "base",
        "chip_added": "added",
        "model_card": "model card",
        "direct": "direct",
        "hf_repo": "hf repo",
        "files_s": "files, hashes, mirrors",
        "copy": "copy",
        "copied": "copied",
        "why_h": "Why this site exists",
        "why_p": "To keep these models available and verifiable. It is not a Hugging "
                 "Face alternative; Hugging Face is one of our mirrors. But these models "
                 "answer questions a state censors, so no single host gets to be the chokepoint.",
        "features": [
            ("No single point of takedown",
             "Independent mirrors plus web-seeded torrents. Works where huggingface.co is blocked."),
            ("Signed, not trusted",
             "sha256-pinned files, minisign-signed manifests. The signature is the trust root, not the host."),
            ("Agent-ready",
             "No gates, no auth. JSON index, <code>--json</code> everywhere, an MCP server."),
            ("Drop-in",
             "Installs into the Hugging Face cache; GGUFs run straight in Ollama."),
        ],
        "faq_h": "FAQ",
        "faq": [
            ("Why not just download these from Hugging Face?",
             "You can; every card links there. This page exists for when that fails: "
             "huggingface.co is blocked in mainland China, and any host can gate or "
             "remove a model. The CLI fails over across mirrors and verifies every byte."),
            ("Why should I trust the files?",
             "Every file is sha256-pinned in a minisign-signed manifest and re-hashed "
             "before install. Publisher keys pin on first use; the official key also "
             "ships inside the pip package. Use <code>--require-signature</code>."),
            ("What if a mirror goes down?",
             "Nothing visible: the CLI fails over, torrents carry web seeds so they work "
             "at zero peers, and the index and this page are mirrored on GitHub and Cloudflare R2."),
            ("Can I help?",
             "<code>unmuzzle seed</code> seeds everything you downloaded until you stop "
             "it. New mirrors are one PR: upload the files anywhere static, append the "
             "URL to the entry's <code>mirrors.http</code>."),
            ("Is the distribution machinery reusable?",
             'Yes: the format and protocol are open (<a href="{repo}/blob/main/SPEC.md">SPEC.md</a>, '
             '<a href="{repo}/blob/main/AGENTS.md">AGENTS.md</a>), and a fork can run its '
             "own index with its own key. A byproduct, not the product."),
        ],
        "trust_h": "Trust root",
        "trust_p": "All releases are minisign-signed with this key. It is pinned inside "
                   "the pip package itself, so no index host alone can substitute it.",
        "foot1": 'unmuzzle is open source (MIT): <a href="{repo}">{repo_short}</a> &middot; '
                 'index: <a href="{repo}/blob/main/index/index.json">index.json</a> &middot; '
                 "generated from the signed index, {date}",
        "foot2": 'Mirrors of this page and the index (if GitHub is unreachable): '
                 '<a href="{r2}/{file}">site</a> &middot; <a href="{r2}/index.json">index.json</a> &middot; '
                 "point the CLI at any index copy with <code>--index</code> or <code>UNMUZZLE_INDEX</code>",
    },
    "zh": {
        "lang": "zh",
        "file": "zh.html",
        "other_file": "./",
        "other_label": "EN",
        "title": "unmuzzle：诚实回答的开源中文模型",
        "meta": "对 Qwen 与 DeepSeek 微调，使其如实回答被审查的政治话题；基座、消融版与微调版全量对比基准；"
                "签名镜像与种子分发，任何单一托管方都无法下架。",
        "og": "开源中文模型，经微调后诚实回答被审查的政治话题。有基准，有签名，抗审查分发。",
        "nav": [("#benchmarks", "基准测试"), ("#models", "模型"), ("#why", "缘由"),
                ("#faq", "常见问题"), ("#trust", "信任根")],
        "tagline": "开源中文模型，经微调后诚实回答被审查的政治话题。有完整基准测试。"
                   "分布式分发，任何单一托管方都无法让它们下线。",
        "run7b": "在任意 8 GB 内存的机器上运行 7B：",
        "optional": "可选：<code>aria2</code> 用于种子下载，<code>minisign</code> 用于签名校验。",
        "bench_h": "基准测试",
        "bench_intro": "留出的 265 题基准：被审查话题的事实、虚构话题的诚实性陷阱、中性对照题。"
                       "跨家族大模型评审，以标准答案为锚。消融版为 huihui-ai 对相同基座的 "
                       "abliteration（当前主流的“去审查”做法）。",
        "col_factual": "事实准确率（审查话题）",
        "col_fab": "编造率（虚构话题）",
        "col_base": "基座",
        "col_abl": "消融版",
        "col_ours": "unmuzzle",
        "takeaway": "消融不增加知识，还会破坏校准：消融版 14B 的编造率是基座的六倍。"
                    "微调后的模型对无从知晓的问题诚实弃答率达 91–100%，中性事实保持 97–100%，"
                    "且从不过度拒答真实事实。",
        "method_s": "方法说明",
        "method": "微调语料约 1,300 组对照式中文问答，在前沿模型（Claude）协助下整理；"
                  "属于窄域行为修正，并非蒸馏。基准与训练数据不重叠且已去重，各组同题同评审。"
                  "标准基准（CMMLU、C-Eval、MMLU、GSM8K，基座对比微调）结果正在整理，完成后发布于此。",
        "models_h": "模型",
        "models_line": "{n} 个模型，每个条目均经签名。CLI 在安装前校验签名与每一个字节。",
        "badge": {
            "unmuzzle/qwen2.5-72b-honesty-lora": "最强",
            "unmuzzle/qwen2.5-7b-honesty": "8 GB 笔记本可跑",
        },
        "chip_base": "基座",
        "chip_added": "收录于",
        "model_card": "模型卡",
        "direct": "直连",
        "hf_repo": "HF 仓库",
        "files_s": "文件、哈希、镜像",
        "copy": "复制",
        "copied": "已复制",
        "why_h": "为什么有这个站",
        "why_p": "为了让这些模型始终可获取、可验证。这不是 Hugging Face 的替代品，"
                 "Hugging Face 是我们的镜像之一。但这些模型回答的是被国家审查的问题，"
                 "不能让任何单一托管方成为咽喉。",
        "features": [
            ("无单点下架",
             "多个独立镜像，加带 web seed 的种子。huggingface.co 被封锁也能用。"),
            ("信签名，不信托管方",
             "文件以 sha256 锁定，清单以 minisign 签名。信任根是签名，不是托管方。"),
            ("对 AI 代理友好",
             "无门槛、无登录。JSON 索引，所有命令支持 <code>--json</code>，自带 MCP 服务器。"),
            ("即装即用",
             "直接装进 Hugging Face 缓存；GGUF 可直接在 Ollama 运行。"),
        ],
        "faq_h": "常见问题",
        "faq": [
            ("为什么不直接从 Hugging Face 下载？",
             "可以，每张卡片都有链接。这个页面是为它失效的时候准备的：huggingface.co "
             "在中国大陆被封锁，任何托管方也都可能设限或下架模型。CLI 会在镜像间自动切换，"
             "并校验每一个字节。"),
            ("凭什么信任这些文件？",
             "每个文件的 sha256 都锁定在 minisign 签名的清单里，安装前重新校验。"
             "发布者密钥首次使用即固定；官方密钥同时内置在 pip 包中。请使用 "
             "<code>--require-signature</code>。"),
            ("镜像挂了怎么办？",
             "无感知：CLI 自动切换镜像，种子带 web seed（零做种也能下载），"
             "索引和本页在 GitHub 与 Cloudflare R2 双镜像。"),
            ("我能帮上什么忙？",
             "<code>unmuzzle seed</code> 会持续做种你下载过的模型，直到你停止它。"
             "新增镜像只需一个 PR：把文件传到任意静态托管，把地址加进条目的 "
             "<code>mirrors.http</code>。"),
            ("这套分发机制可以复用吗？",
             '可以：格式与协议完全公开（<a href="{repo}/blob/main/SPEC.md">SPEC.md</a>、'
             '<a href="{repo}/blob/main/AGENTS.md">AGENTS.md</a>），fork 后可用自己的密钥'
             "运行独立索引。但那是副产品，不是产品。"),
        ],
        "trust_h": "信任根",
        "trust_p": "所有发布均以此 minisign 密钥签名。密钥同时固化在 pip 包内，"
                   "任何索引托管方都无法单独替换。",
        "foot1": 'unmuzzle 开源（MIT）：<a href="{repo}">{repo_short}</a> &middot; '
                 '索引：<a href="{repo}/blob/main/index/index.json">index.json</a> &middot; '
                 "由签名索引生成，{date}",
        "foot2": '本页与索引的镜像（GitHub 不可达时）：<a href="{r2}/{file}">站点</a> &middot; '
                 '<a href="{r2}/index.json">index.json</a> &middot; '
                 "用 <code>--index</code> 或 <code>UNMUZZLE_INDEX</code> 指向任意索引副本",
    },
}


def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def bench_table(t: dict) -> str:
    rows = []
    for label, factual, fab, flag in BENCH:
        cells = []
        for group_i, triple in enumerate((factual, fab)):
            for i, v in enumerate(triple):
                cls = ' class="group"' if group_i == 1 and i == 0 else ""
                txt = "&ndash;" if v is None else f"{v}%"
                if i == 2 and v is not None:
                    txt = f"<strong>{txt}</strong>"
                cells.append(f"<td{cls}>{txt}</td>")
        name = f"<strong>{label}</strong>" if flag else label
        rows.append(f"<tr><td>{name}</td>{''.join(cells)}</tr>")
    sub = (f'<th>{t["col_base"]}</th><th>{t["col_abl"]}</th><th>{t["col_ours"]}</th>')
    sub2 = (f'<th class="group">{t["col_base"]}</th><th>{t["col_abl"]}</th><th>{t["col_ours"]}</th>')
    return f'''<div class="tablewrap"><table>
<thead>
<tr><th></th><th colspan="3">{t["col_factual"]}</th><th colspan="3" class="group">{t["col_fab"]}</th></tr>
<tr><th></th>{sub}{sub2}</tr>
</thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table></div>'''


def model_links(m: dict, t: dict) -> str:
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
        out.append(f'<a href="{e(url)}">{t["direct"]}: {e(label)}</a>')
        if "huggingface.co" in host and "/resolve/" in base:
            out.append(f'<a href="{e(base.split("/resolve/")[0])}">{t["hf_repo"]}</a>')
    if mirrors.get("torrent"):
        out.append(f'<a href="{e(mirrors["torrent"])}">.torrent</a>')
    if mirrors.get("magnet"):
        out.append(f'<a href="{e(mirrors["magnet"])}">magnet</a>')
    return " &middot; ".join(out)


def model_card(m: dict, cid: int, t: dict) -> str:
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
    badge = t["badge"].get(m["name"], "")
    desc = m.get("description", "")
    mcard = re.search(r"(?:Model card|Details): (\S+)", desc)
    if t["lang"] == "zh" and m["name"] in ZH_DESC:
        desc = ZH_DESC[m["name"]]
    else:
        desc = re.sub(r"\s*Corpus curated with frontier-model \(Claude\) assistance\.", "", desc)
        desc = re.sub(r"\s*(?:Model card|Details): \S+", "", desc).strip()
    links = model_links(m, t)
    if mcard:
        links = (f'<a href="{e(mcard.group(1).rstrip("."))}">{t["model_card"]}</a>'
                 f" &middot; " + links)
    badge_html = f'<span class="chip badge">{e(badge)}</span>' if badge else ""
    return f'''
<div class="card">
  <h3>{e(m["name"])}</h3>
  <div class="chips">
    {badge_html}<span class="chip license">{e(m.get("license", "unknown"))}</span>
    <span class="chip">{human_size(total)}</span>
    <span class="chip">{t["chip_base"]}: {e(m.get("base_model", "?"))}</span>
    <span class="chip">{t["chip_added"]} {e(m.get("added", "?"))}</span>
    {"".join(f'<span class="chip">{e(tag)}</span>' for tag in m.get("tags", []))}
  </div>
  <p>{e(desc)}</p>
  <p class="links">{links}</p>
  <div class="getline">
    <pre><code id="cmd-{cid}">unmuzzle get {e(m["name"])} --require-signature --dest ./models</code></pre>
    <button onclick="copy(this, 'cmd-{cid}')">{t["copy"]}</button>
  </div>
  <details>
    <summary>{t["files_s"]}</summary>
    <pre><code>{e(chr(10).join(lines))}</code></pre>
  </details>
</div>
'''


def render(lang: str, models: list, pubkey: str) -> str:
    t = STR[lang]
    repo_short = REPO.removeprefix("https://")
    date = datetime.date.today().isoformat()
    nav = "\n  ".join(f'<a class="links sect" href="{h}">{label}</a>' for h, label in t["nav"])
    cards = "\n".join(model_card(m, i, t) for i, m in enumerate(models))
    features = "\n".join(
        f'  <div class="feature">\n    <h3>{h}</h3>\n    <p>{p}</p>\n  </div>'
        for h, p in t["features"]
    )
    faq = "\n".join(
        f"<details>\n  <summary>{q}</summary>\n  <p>{a.format(repo=REPO)}</p>\n</details>"
        for q, a in t["faq"]
    )
    js = JS.replace("__COPIED__", t["copied"]).replace("__COPY__", t["copy"])
    url = SITE if lang == "en" else SITE + "zh.html"
    return f'''<!doctype html>
<html lang="{t["lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t["title"]}</title>
<meta name="description" content="{t["meta"]}">
<meta property="og:title" content="unmuzzle">
<meta property="og:description" content="{t["og"]}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<link rel="alternate" hreflang="en" href="{SITE}">
<link rel="alternate" hreflang="zh" href="{SITE}zh.html">
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>

<nav><div class="wrap">
  <div class="wordmark">un<span>muzzle</span></div>
  {nav}
  <div class="spacer"></div>
  <a class="links" href="{t["other_file"]}">{t["other_label"]}</a>
  <a class="links" href="{REPO}">github</a>
</div></nav>

<div class="wrap">

<header class="hero">
  <h1>un<span>muzzle</span></h1>
  <p class="tagline">{t["tagline"]}</p>
  <p class="dim" style="margin-top:1rem">{t["run7b"]}</p>
  <div class="quickstart">
    <pre><code id="qs">pip install unmuzzle
unmuzzle get unmuzzle/qwen2.5-7b-honesty --require-signature --dest m && cd m
ollama create unmuzzle-7b -f Modelfile.unmuzzle7b && ollama run unmuzzle-7b</code></pre>
    <button onclick="copy(this, 'qs')">{t["copy"]}</button>
  </div>
  <p class="dim" style="margin-top:.6rem;font-size:.85rem">{t["optional"]}</p>
</header>

<h2 id="benchmarks">{t["bench_h"]}</h2>
<p class="dim">{t["bench_intro"]}</p>
{bench_table(t)}
<p class="dim">{t["takeaway"]}</p>
<details class="method">
  <summary>{t["method_s"]}</summary>
  <p>{t["method"]}</p>
</details>

<h2 id="models">{t["models_h"]}</h2>
<p class="dim">{t["models_line"].format(n=len(models))}</p>
{cards}

<h2 id="why">{t["why_h"]}</h2>
<p>{t["why_p"]}</p>
<div class="grid">
{features}
</div>

<h2 id="faq">{t["faq_h"]}</h2>

{faq}

<h2 id="trust">{t["trust_h"]}</h2>
<pre><code>{html.escape(pubkey)}</code></pre>
<p class="dim">{t["trust_p"]}</p>

<footer>
  <p>{t["foot1"].format(repo=REPO, repo_short=repo_short, date=date)}</p>
  <p>{t["foot2"].format(r2=R2, file=t["file"])}</p>
</footer>

</div>
<script>{js}</script>
</body>
</html>
'''


def main() -> None:
    idx = json.loads(INDEX.read_text())
    models = idx["models"]
    if isinstance(models, dict):
        models = list(models.values())
    models.sort(key=lambda m: (RANK.get(m["name"], 99), m.get("added", "")))
    pubkey = models[0].get("publisher_pubkey", "unknown") if models else "unknown"

    DOCS.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "zh"):
        out = DOCS / STR[lang]["file"]
        out.write_text(render(lang, models, pubkey))
        print(f"wrote {out} ({len(models)} models)")


if __name__ == "__main__":
    main()
