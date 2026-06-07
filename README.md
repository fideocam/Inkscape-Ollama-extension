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

- Inkscape **1.2+** (uses `inkex` and GTK 3)
- [Ollama](https://ollama.com) running locally with a model pulled (e.g. `ollama pull llama3.2`)

## Usage

- Type a prompt and click **Ask InkscapeGPT**. The extension sends the system prompt, your text, and a text digest of the document (truncated by **Max document chars** in settings).
- Use **Review design** (or **Extensions → InkscapeGPT → Review with InkscapeGPT…**) for analysis-focused prompts without automatic edits unless the model returns actions.
- If the model ends its reply with `{"actions":[...]}`, those actions are applied to the open document.
- **Stop** sets a cancel flag (the HTTP stream may not stop instantly).
- Settings are stored in `~/.config/inkscape-ollama/config.json` (or `%APPDATA%\inkscape-ollama\` on Windows).

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
| UI | `inkscape_gpt.py` | GTK dialog + worker thread |

## Tests

Fast unit tests (no Inkscape required):

```bash
pip install -r requirements-dev.txt
pytest
```

## License

MIT
