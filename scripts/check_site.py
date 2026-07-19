#!/usr/bin/env python3
"""Verification loop for the unmuzzle site. Zero dependencies.

Checks the generated docs/ pages against the user-friendliness contract:

  structure   both languages exist, same sections, same model cards,
              every nav anchor resolves, no unformatted {placeholders}
  content     exactly ONE benchmark table, quickstart block present,
              trust key present, language toggle cross-links correct
  links       every internal link resolves; with --network, every external
              link answers < 400 (HEAD, then ranged GET fallback)
  size        each page under 80 KB (self-contained, fast on bad links)

Exit 0 = pass. Any failure prints FAIL lines and exits 1.

Usage:  python3 scripts/check_site.py [--network]
"""
from __future__ import annotations

import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
PAGES = {"en": DOCS / "index.html", "zh": DOCS / "zh.html"}

fails: list[str] = []
warns: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print(f"[FAIL] {msg}")


def ok(msg: str) -> None:
    print(f"[pass] {msg}")


class Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.tables = 0
        self.buttons = 0
        self.lang = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        d = dict(attrs)
        if "id" in d:
            self.ids.add(d["id"])
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        if tag == "table":
            self.tables += 1
        if tag == "button":
            self.buttons += 1
        if tag == "html":
            self.lang = d.get("lang", "")


def scan(path: Path) -> Scan:
    s = Scan()
    s.feed(path.read_text())
    return s


def main() -> int:
    network = "--network" in sys.argv
    scans: dict[str, Scan] = {}

    for lang, path in PAGES.items():
        if not path.exists():
            fail(f"{lang}: {path.name} missing")
            continue
        h = path.read_text()
        s = scan(path)
        scans[lang] = s

        if s.lang != lang:
            fail(f"{lang}: html lang attr is '{s.lang}'")
        if re.search(r"\{[a-z_]+\}", h):
            fail(f"{lang}: unformatted placeholder: "
                 f"{re.search(r'{[a-z_]+}', h).group(0)}")
        if s.tables != 1:
            fail(f"{lang}: expected exactly 1 table, found {s.tables}")
        kb = len(h.encode()) / 1024
        if kb > 80:
            fail(f"{lang}: page is {kb:.0f} KB (limit 80)")
        if "unmuzzle get unmuzzle/qwen2.5-7b-honesty" not in h:
            fail(f"{lang}: quickstart block missing")
        if "RWQ" not in h:
            fail(f"{lang}: trust key missing")

        # every internal anchor a nav or body link points at must exist
        for href in s.hrefs:
            if href.startswith("#") and href[1:] not in s.ids:
                fail(f"{lang}: dangling anchor {href}")

        ok(f"{lang}: structure, size {kb:.0f} KB, {s.tables} table, "
           f"{len(s.ids)} ids, {len(s.hrefs)} links")

    if set(scans) == {"en", "zh"}:
        en, zh = scans["en"], scans["zh"]
        if en.ids != zh.ids:
            fail(f"language parity: ids differ: {en.ids ^ zh.ids}")
        if en.tables != zh.tables or en.buttons != zh.buttons:
            fail("language parity: table/button counts differ")
        en_h = PAGES["en"].read_text()
        zh_h = PAGES["zh"].read_text()
        if 'href="zh.html">中文</a>' not in en_h:
            fail("en: language toggle to zh.html missing")
        if 'href="./">EN</a>' not in zh_h:
            fail("zh: language toggle to ./ missing")
        # same model cards in both
        cards_en = set(re.findall(r"unmuzzle get (unmuzzle/\S+) ", en_h))
        cards_zh = set(re.findall(r"unmuzzle get (unmuzzle/\S+) ", zh_h))
        if cards_en != cards_zh:
            fail(f"language parity: cards differ: {cards_en ^ cards_zh}")
        else:
            ok(f"language parity: {len(cards_en)} cards, toggles, ids")

    if network and not fails:
        seen: set[str] = set()
        for lang, s in scans.items():
            for href in s.hrefs:
                if not href.startswith("http") or href in seen:
                    continue
                if href.startswith("magnet:"):
                    continue
                seen.add(href)
                try:
                    req = urllib.request.Request(href, method="HEAD",
                                                 headers={"User-Agent": "unmuzzle-check"})
                    code = urllib.request.urlopen(req, timeout=20).status
                except Exception:
                    try:
                        req = urllib.request.Request(
                            href, headers={"User-Agent": "unmuzzle-check",
                                           "Range": "bytes=0-0"})
                        code = urllib.request.urlopen(req, timeout=20).status
                    except Exception as exc:
                        fail(f"link dead: {href} ({exc})")
                        continue
                if code >= 400:
                    fail(f"link {code}: {href}")
        ok(f"network: {len(seen)} external links checked")

    if fails:
        print(f"\n== FAIL: {len(fails)} problem(s)")
        return 1
    print("\n== PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
