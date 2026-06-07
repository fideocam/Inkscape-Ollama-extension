"""Persistent settings for InkscapeGPT (stored outside Inkscape)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "base_url": "http://127.0.0.1:11434",
    "model": "llama3.2:latest",
    "num_ctx": 0,
    "max_context_chars": 48_000,
    "request_timeout": 600.0,
    "auto_wake_ollama": True,
    "preload_model": True,
}


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "inkscape-ollama"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    data = dict(DEFAULTS)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save_config(data: dict[str, Any]) -> None:
    merged = dict(DEFAULTS)
    merged.update(data)
    config_path().write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
