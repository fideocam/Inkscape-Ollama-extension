"""Parse assistant JSON action lists (no Inkscape dependencies)."""

from __future__ import annotations

import json
from json import JSONDecoder
from typing import Any


def extract_actions_json(assistant_text: str) -> list[dict[str, Any]]:
    text = assistant_text.strip()
    markers = ('{"actions"', "{'actions'")
    idx = -1
    for marker in markers:
        j = text.rfind(marker)
        idx = max(idx, j)
    if idx == -1:
        return []
    snippet = text[idx:]
    try:
        obj, _end = JSONDecoder().raw_decode(snippet)
    except json.JSONDecodeError:
        return []

    actions = obj.get("actions")
    if not isinstance(actions, list):
        return []
    out: list[dict[str, Any]] = []
    for item in actions:
        if isinstance(item, dict) and isinstance(item.get("op"), str):
            out.append(item)
    return out
