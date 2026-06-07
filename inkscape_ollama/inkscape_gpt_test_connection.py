#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test Ollama connection using saved InkscapeGPT settings."""

from __future__ import annotations

import sys
from pathlib import Path

import inkex

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config  # noqa: E402
from ollama_client import test_ollama_connection  # noqa: E402


class InkscapeGPTTestConnectionExtension(inkex.EffectExtension):
    """Test Ollama using values from config.json."""

    def load_raw(self) -> None:
        self.document = None
        self.svg = None

    def save_raw(self, ret) -> None:
        return

    def has_changed(self, ret) -> bool:
        return False

    def effect(self) -> None:
        config = load_config()
        summary = test_ollama_connection(
            str(config.get("base_url", "")),
            str(config.get("model", "")),
            try_launch=bool(config.get("auto_wake_ollama")),
        )
        raise inkex.AbortExtension(summary)


if __name__ == "__main__":
    InkscapeGPTTestConnectionExtension().run()
