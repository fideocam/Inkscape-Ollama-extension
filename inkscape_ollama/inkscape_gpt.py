#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InkscapeGPT — ask local Ollama to create, change, or review SVG documents.

Uses Inkscape's built-in extension dialog (no separate GTK window). This avoids
PyGObject/GioUnix issues in Inkscape's bundled Python on macOS.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

import inkex

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_actions import apply_actions, extract_actions_json  # noqa: E402
from config import config_dir, load_config  # noqa: E402
from context_builder import build_document_digest  # noqa: E402
from ollama_client import (  # noqa: E402
    chat_completion,
    ensure_ollama_ready,
    resolve_model_name,
)
from system_prompt import (  # noqa: E402
    SYSTEM_PROMPT,
    build_review_mode_user_message,
    build_user_message,
)

_LAST_RESPONSE = config_dir() / "last_response.txt"

_DEFAULT_PROMPT = (
    'Create: Add centered "Hello world!" text in the middle of the document (36 pt).'
)


def _log(message: str) -> None:
    """Append to log file (never shown as an Inkscape error dialog)."""
    try:
        path = config_dir() / "inkscape_gpt.log"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message if message.endswith("\n") else message + "\n")
    except OSError:
        pass


def _report_error(message: str) -> None:
    """Show a real failure in Inkscape's extension error dialog."""
    err = sys.__stderr__
    if err is None:
        return
    try:
        err.write(message if message.endswith("\n") else message + "\n")
    except (OSError, TypeError):
        pass


def _save_last_response(text: str) -> Path:
    path = _LAST_RESPONSE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _normalize_prompt(prompt: str) -> str:
    """Use the first non-empty line; strip Create/Change/Review prefixes."""
    for line in prompt.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        for prefix in ("create:", "change:", "review:"):
            if lower.startswith(prefix):
                return stripped[len(prefix) :].strip()
        return stripped
    return ""


def _is_review_prompt(prompt: str) -> bool:
    first = next((ln.strip().lower() for ln in prompt.splitlines() if ln.strip()), "")
    return first.startswith("review:") or first.startswith("review ")


def _execute(
    svg: inkex.SvgDocumentElement,
    selection: list[Any],
    prompt: str,
) -> None:
    raw_prompt = (prompt or "").strip()
    if not raw_prompt:
        raise inkex.AbortExtension("Enter a prompt.")
    prompt = _normalize_prompt(raw_prompt)
    if not prompt:
        raise inkex.AbortExtension("Enter a prompt.")

    config = load_config()
    base_url = str(config.get("base_url", "http://127.0.0.1:11434"))
    model = str(config.get("model", "llama3.2:latest"))
    num_ctx = int(config.get("num_ctx", 0) or 0)
    timeout = float(config.get("request_timeout", 600))
    max_chars = int(config.get("max_context_chars", 48000))

    model = resolve_model_name(base_url, model)

    if config.get("auto_wake_ollama") or config.get("preload_model"):
        ensure_ollama_ready(
            base_url,
            model,
            preload_model=bool(config.get("preload_model")),
            num_ctx=num_ctx,
            try_launch=bool(config.get("auto_wake_ollama")),
        )

    digest = build_document_digest(svg, selection, max_chars)
    if _is_review_prompt(raw_prompt):
        user_msg = build_review_mode_user_message(digest, prompt)
    else:
        user_msg = build_user_message(digest, prompt)

    text = chat_completion(
        base_url,
        model,
        SYSTEM_PROMPT,
        user_msg,
        num_ctx=num_ctx,
        timeout=timeout,
    )

    response_path = _save_last_response(text)

    actions = extract_actions_json(text)
    if actions:
        logs = apply_actions(svg, actions)
        summary = f"applied {len(actions)} action(s)"
        if logs:
            summary += ": " + "; ".join(logs[:12])
            if len(logs) > 12:
                summary += f" (+{len(logs) - 12} more)"
        _log(f"InkscapeGPT {summary}. Full reply: {response_path}")
    else:
        _log(f"InkscapeGPT analysis saved to {response_path}")


class InkscapeGPTExtension(inkex.EffectExtension):
    """Ask InkscapeGPT via Inkscape's extension dialog."""

    def add_arguments(self, pars):
        pars.add_argument("--prompt", type=str, default=_DEFAULT_PROMPT, help="Prompt for Ollama")

    def effect(self) -> None:
        try:
            selection = list(self.svg.selection)
            _execute(
                self.svg,
                selection,
                getattr(self.options, "prompt", ""),
            )
        except inkex.AbortExtension:
            raise
        except Exception as exc:
            _report_error(f"InkscapeGPT failed: {exc}\n{traceback.format_exc()}")
            raise


def _run_extension(extension_cls: type) -> None:
    extension_cls().run()


if __name__ == "__main__":
    _run_extension(InkscapeGPTExtension)
