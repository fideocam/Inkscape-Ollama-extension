# InkscapeGPT

Inkscape extension in the spirit of **[ArchiGPT](https://github.com/)** and **BlenderGPT**: chat with a local **[Ollama](https://ollama.com)** model using a **document digest** and **selection**, then optionally apply **small JSON-defined SVG edits** (rectangles, ellipses, paths, text, transforms, styles, layers).

## Install

Inkscape loads extensions from its **user extensions** folder. Find the exact path in Inkscape: **Edit → Preferences → System → User extensions**.

### Option A: Symlink (recommended for development)

A symlink lets you edit the extension in this repo and see changes after restarting Inkscape (no copy step).

**macOS** (adjust the repo path if yours differs):

```bash
mkdir -p "$HOME/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions"

ln -sfn "/Users/Raino.Annala/InkscapeR/Inkscape-Ollama-extension/inkscape_ollama" \
  "$HOME/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkscape_ollama"
```

**Linux:**

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/inkscape/extensions"

ln -sfn "/path/to/Inkscape-Ollama-extension/inkscape_ollama" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/inkscape/extensions/inkscape_ollama"
```

Verify the link:

```bash
ls -la "$HOME/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkscape_ollama"
# should show inkscape_ollama -> .../Inkscape-Ollama-extension/inkscape_ollama
```

To remove the symlink later:

```bash
rm "$HOME/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/inkscape_ollama"
```

### Option B: Copy (one-time install)

```bash
./scripts/install.sh
```

Or copy the `inkscape_ollama/` folder manually into the user extensions directory:

- **macOS:** `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
- **Linux:** `~/.config/inkscape/extensions/`
- **Windows:** `%APPDATA%\inkscape\extensions\`

### After install

1. Restart Inkscape (extensions are loaded at startup).
2. Open **Extensions → InkscapeGPT → InkscapeGPT…**

## Requirements

- Inkscape **1.2+** (uses `inkex`)
- [Ollama](https://ollama.com) running locally with a model pulled (e.g. `ollama pull llama3.2`)

## Usage

InkscapeGPT uses Inkscape’s **built-in extension dialog** — a single prompt field for **InkscapeGPT…**, and a separate **InkscapeGPT Settings…** menu item for Ollama options.

1. Choose **Extensions → InkscapeGPT → InkscapeGPT…**
2. Edit the **Prompt** field (hover for Create / Change / Review examples), then click **Apply**.
3. Model, URL, and related options: **Extensions → InkscapeGPT → InkscapeGPT Settings…** (stored in `~/.config/inkscape-ollama/config.json`). With **Test connection on Apply** enabled, Apply checks Ollama and shows the result.
4. Quick check without changing settings: **Extensions → InkscapeGPT → Test Ollama Connection** (uses saved config).
5. SVG edits appear on the canvas; text-only replies are saved to `~/.config/inkscape-ollama/last_response.txt`.
- If the model ends its reply with `{"actions":[...]}`, those actions are applied to the open document.
- The full text of each reply is saved to `~/.config/inkscape-ollama/last_response.txt`.
- Settings from the dialog are stored in `~/.config/inkscape-ollama/config.json` (or `%APPDATA%\inkscape-ollama\` on Windows).

Edit **`inkscape_ollama/prompts/system_prompt_rules.txt`** for natural-language behaviour; **`action_schema.txt`** for allowed JSON ops. Restart Inkscape after prompt changes.

## Capabilities (SVG)

- **Create:** rect, ellipse, line, path, text
- **Modify:** transform, dimensions, style, rename, duplicate
- **Structure:** layers, groups, move to layer, page size
- **Delete:** remove elements by id

Complex path booleans, live path effects, and font management are not in the allowlist yet.

## Architecture

Same three-layer design as BlenderGPT:

| Layer | Module | Role |
|-------|--------|------|
| Transport | `ollama_client.py` | Ollama HTTP (stdlib only) |
| Prompting | `system_prompt.py`, `context_builder.py` | Rules + document digest |
| Mutation | `apply_actions.py` | Parse JSON, apply allowlisted SVG ops |
| UI | `inkscape_gpt.py`, `.inx` files | Inkscape extension dialog + `effect()` |

```bash
chmod +x scripts/test_from_terminal.sh
./scripts/test_from_terminal.sh
```

## Testing in Inkscape

1. Open any document (even a blank page).
2. Choose **Extensions → InkscapeGPT → InkscapeGPT…**
3. Enter a prompt and click **Apply**.
4. Wait for the Ollama call to finish; read the result message and check `~/.config/inkscape-ollama/last_response.txt` for the full reply.

If the extension fails, Inkscape may show an error dialog. You can also run unit tests locally (below) without Inkscape.

## Tests

Fast unit tests (no Inkscape required):

```bash
pip install -r requirements-dev.txt
pytest
```

## License

MIT
