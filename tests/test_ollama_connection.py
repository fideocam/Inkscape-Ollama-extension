"""Tests for Ollama connection helper (no network)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ollama_client import test_ollama_connection


@patch("ollama_client.get_model_context_settings", return_value={"summary": "Context OK."})
@patch("ollama_client.resolve_model_name", return_value="llama3.2:latest")
@patch("ollama_client.list_model_names", return_value=["llama3.2:latest"])
@patch("ollama_client.wait_for_connection", return_value=True)
def test_test_ollama_connection_success(_wait, _list, _resolve, _ctx):
    msg = test_ollama_connection("http://127.0.0.1:11434", "llama3.2:latest", try_launch=False)
    assert "Connected to Ollama" in msg
    assert "llama3.2:latest" in msg


@patch("ollama_client.wait_for_connection", return_value=False)
def test_test_ollama_connection_unreachable(_wait):
    with pytest.raises(RuntimeError, match="not reachable"):
        test_ollama_connection("http://127.0.0.1:11434", "llama3.2:latest", try_launch=False)
