#!/usr/bin/env bash
# Локальные Font Awesome для /panel-static/ (после git clone папки panel_static может не быть).
set -euo pipefail
cd "$(dirname "$0")"

FA_VER="6.0.0-beta3"
BASE="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/${FA_VER}"
mkdir -p panel_static/webfonts

if command -v curl >/dev/null 2>&1; then
  DL=(curl -fsSL)
elif command -v wget >/dev/null 2>&1; then
  DL=(wget -qO-)
else
  echo "install_panel_static: нужен curl или wget"
  exit 1
fi

echo "[panel_static] Font Awesome ${FA_VER}…"
"${DL[@]}" "${BASE}/css/all.min.css" > panel_static/all.min.css.tmp
# Пути шрифтов: от /panel-static/all.min.css → /panel-static/webfonts/
sed 's|\.\./webfonts/|/panel-static/webfonts/|g' panel_static/all.min.css.tmp > panel_static/all.min.css
rm -f panel_static/all.min.css.tmp

for f in fa-solid-900.woff2 fa-regular-400.woff2 fa-brands-400.woff2; do
  echo "[panel_static] ${f}…"
  curl -fsSL -o "panel_static/webfonts/${f}" "${BASE}/webfonts/${f}" 2>/dev/null \
    || wget -q -O "panel_static/webfonts/${f}" "${BASE}/webfonts/${f}"
done

echo "[panel_static] OK: $(wc -c < panel_static/all.min.css) bytes CSS"
