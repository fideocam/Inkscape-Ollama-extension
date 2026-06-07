#!/usr/bin/env bash
# Install InkscapeGPT into the Inkscape user extensions folder.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/inkscape_ollama" && pwd)"

if [[ "$(uname)" == "Darwin" ]]; then
  DEST="${HOME}/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkscape_ollama"
else
  DEST="${XDG_CONFIG_HOME:-${HOME}/.config}/inkscape/extensions/inkscape_ollama"
fi

mkdir -p "$(dirname "$DEST")"
if [[ -e "$DEST" ]]; then
  echo "Removing existing install: $DEST"
  rm -rf "$DEST"
fi

cp -R "$SRC" "$DEST"
echo "Installed InkscapeGPT to:"
echo "  $DEST"
echo ""
echo "Restart Inkscape, then use Extensions → InkscapeGPT → InkscapeGPT…"
