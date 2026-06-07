#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InkscapeGPT settings — save Ollama options and optionally test the connection."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import inkex

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import apply_extension_options, config_path, save_config  # noqa: E402
from ollama_client import test_ollama_connection  # noqa: E402


def _log(message: str) -> None:
    try:
        from config import config_dir

        path = config_dir() / "inkscape_gpt.log"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message if message.endswith("\n") else message + "\n")
    except OSError:
        pass


def _report_error(message: str) -> None:
    err = sys.__stderr__
    if err is None:
        return
    try:
        err.write(message if message.endswith("\n") else message + "\n")
    except (OSError, TypeError):
        pass


class _NoDocumentExtension(inkex.EffectExtension):
    """Effect that does not read or write the open SVG."""

    def load_raw(self) -> None:
        self.document = None
        self.svg = None

    def save_raw(self, ret) -> None:
        return

    def has_changed(self, ret) -> bool:
        return False


class InkscapeGPTSettingsExtension(_NoDocumentExtension):
    """Save InkscapeGPT settings."""

    def add_arguments(self, pars):
        pars.add_argument("--model", type=str, default="llama3.2:latest", help="Ollama model")
        pars.add_argument(
            "--base_url", type=str, default="http://127.0.0.1:11434", help="Ollama URL"
        )
        pars.add_argument(
            "--max_chars", type=int, default=48000, help="Max document digest characters"
        )
        pars.add_argument(
            "--auto_wake",
            type=inkex.Boolean,
            default=True,
            help="Try to start Ollama if not running",
        )
        pars.add_argument(
            "--preload",
            type=inkex.Boolean,
            default=True,
            help="Preload the model before chat",
        )
        pars.add_argument(
            "--test_connection",
            type=inkex.Boolean,
            default=True,
            help="Test Ollama before saving settings",
        )

    def effect(self) -> None:
        try:
            config = apply_extension_options(self.options)
            path = config_path()

            if getattr(self.options, "test_connection", True):
                summary = test_ollama_connection(
                    str(config.get("base_url", "")),
                    str(config.get("model", "")),
                    try_launch=bool(config.get("auto_wake_ollama")),
                )
                save_config(config)
                _log(f"InkscapeGPT settings saved to {path}\n{summary}")
                raise inkex.AbortExtension(f"{summary}\n\nSettings saved to:\n{path}")

            save_config(config)
            _log(f"InkscapeGPT settings saved to {path}")
            raise inkex.AbortExtension(f"Settings saved to:\n{path}")
        except inkex.AbortExtension:
            raise
        except Exception as exc:
            _report_error(f"InkscapeGPT settings failed: {exc}\n{traceback.format_exc()}")
            raise inkex.AbortExtension(f"Settings failed: {exc}") from exc


if __name__ == "__main__":
    InkscapeGPTSettingsExtension().run()
