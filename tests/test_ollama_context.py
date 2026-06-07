"""Tests for Ollama client helpers (no network)."""

from __future__ import annotations

from ollama_client import resolve_context_settings, suggest_max_document_chars


def test_suggest_max_document_chars():
    assert suggest_max_document_chars(32768) > 2000
    assert suggest_max_document_chars(32768) < 500_000


def test_resolve_context_settings_from_model_info():
    data = {"model_info": {"llama.context_length": 131072}, "parameters": "num_ctx 4096"}
    out = resolve_context_settings(data)
    assert out["num_ctx"] == 4096
    assert out["max_document_chars"] > 0
