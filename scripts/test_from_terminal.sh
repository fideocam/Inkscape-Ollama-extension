#!/usr/bin/env bash
# Run InkscapeGPT the same way Inkscape invokes effect extensions.
# Use this when the menu item appears to do nothing.
set -euo pipefail

INK_PYTHON="/Applications/Inkscape.app/Contents/Resources/bin/python3"
EXT_DIR="$(cd "$(dirname "$0")/../inkscape_ollama" && pwd)"
EXT="$EXT_DIR/inkscape_gpt.py"
SAMPLE="$(mktemp /tmp/inkscape-gpt-test.XXXXXX.svg)"

cat >"$SAMPLE" <<'SVG'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <rect id="rect1" x="10" y="10" width="30" height="30" fill="#ff0000"/>
</svg>
SVG

export PYTHONPATH="/Applications/Inkscape.app/Contents/Resources/share/inkscape/extensions:${PYTHONPATH:-}"

echo "Running InkscapeGPT with Inkscape's Python..."
echo "Expected: a separate GTK window titled 'InkscapeGPT' opens and blocks this terminal."
echo "Sample SVG: $SAMPLE"
echo "Log file: $HOME/.config/inkscape-ollama/inkscape_gpt.log"
echo

"$INK_PYTHON" "$EXT" <"$SAMPLE"

echo
echo "Extension finished."
