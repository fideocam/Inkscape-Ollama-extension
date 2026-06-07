"""Unit tests for parsing assistant replies into SVG action lists."""

from __future__ import annotations

from actions_json import extract_actions_json


def test_create_rect_parses():
    text = """Plan:
{"actions":[{"op":"create_rect","id":"box1","x":0,"y":0,"width":100,"height":50}]}"""
    actions = extract_actions_json(text)
    assert len(actions) == 1
    assert actions[0]["op"] == "create_rect"
    assert actions[0]["width"] == 100


def test_delete_elements_parses():
    text = '{"actions":[{"op":"delete_elements","ids":["a","b"]}]}'
    actions = extract_actions_json(text)
    assert actions[0]["ids"] == ["a", "b"]


def test_describe_style_no_json_returns_empty():
    text = "The logo uses two layers and a red fill."
    assert extract_actions_json(text) == []


def test_uses_last_actions_block():
    text = """
{"actions":[{"op":"delete_elements","ids":["old"]}]}
{"actions":[{"op":"create_text","id":"t1","text":"Hi"}]}"""
    actions = extract_actions_json(text)
    assert len(actions) == 1
    assert actions[0]["op"] == "create_text"


def test_invalid_json_returns_empty():
    assert extract_actions_json('{"actions":[broken') == []
