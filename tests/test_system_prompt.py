"""Tests for system prompt assembly."""

from __future__ import annotations

from system_prompt import SYSTEM_PROMPT, build_user_message


def test_system_prompt_contains_rules_and_schema():
    assert "InkscapeGPT" in SYSTEM_PROMPT
    assert "create_rect" in SYSTEM_PROMPT
    assert "Action schema" in SYSTEM_PROMPT


def test_build_user_message_format():
    msg = build_user_message("digest here", "make a red square")
    assert "=== Document digest ===" in msg
    assert "digest here" in msg
    assert "make a red square" in msg
