#!/bin/bash
# Visual review loop for the unmuzzle site.
#
# Renders the built pages (docs/) into screenshots for a design review:
#   {en,zh} x {desktop 1280, narrow 500} x {light, dark}  -> 8 PNGs
#
# Dark mode is rendered by injecting the dark token block as a :root override
# (headless Chrome cannot emulate prefers-color-scheme without CDP).
# Narrow is 500px, not 390: macOS headless Chrome clamps window width to
# ~500, and a 390 request silently captures a cropped 500px render.
#
# Usage:  scripts/visual_review.sh <output-dir>
#
# Review the shots against this rubric (in order):
#   1. Subtract first: anything on screen that isn't earning its place?
#   2. Hierarchy from scale and space only; one accent color, one voice.
#   3. Tables: aligned numerals, quiet rules, readable at narrow width.
#   4. Cards: metadata quieter than content; no pill/badge spam.
#   5. Dark mode: same hierarchy, nothing glows, borders still quiet.
#   6. Both languages: typography holds in CJK (line-height, punctuation).
set -euo pipefail

OUT="${1:?usage: visual_review.sh <output-dir>}"
DOCS="$(cd "$(dirname "$0")/.." && pwd)/docs"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DARK=':root{color-scheme:dark;--bg:#0d1117;--fg:#e6edf3;--dim:#8b949e;--card:#161b22;--border:#30363d;--accent:#f0b429;--code-bg:#1c2128}'

mkdir -p "$OUT"
for lang in en zh; do
  src="$DOCS/index.html"; [ "$lang" = zh ] && src="$DOCS/zh.html"
  cp "$src" "$OUT/$lang-light.html"
  sed "s|</head>|<style>$DARK</style></head>|" "$src" > "$OUT/$lang-dark.html"
  for theme in light dark; do
    for geom in "desktop:1280,2600" "narrow:500,3200"; do
      name="${geom%%:*}"; size="${geom##*:}"
      "$CHROME" --headless --disable-gpu --hide-scrollbars \
        --screenshot="$OUT/$lang-$name-$theme.png" --window-size="$size" \
        "file://$OUT/$lang-$theme.html" 2>/dev/null
    done
  done
done
rm -f "$OUT"/*.html
ls -la "$OUT"
