"""Load system prompt from editable text files under inkscape_ollama/prompts/."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_RULES_FILE = "system_prompt_rules.txt"
_SCHEMA_FILE = "action_schema.txt"


def _read_prompt_file(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"InkscapeGPT prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt_rules() -> str:
    return _read_prompt_file(_RULES_FILE)


def load_action_schema() -> str:
    return _read_prompt_file(_SCHEMA_FILE)


def build_system_prompt() -> str:
    rules = load_system_prompt_rules()
    schema = load_action_schema()
    return f"{rules}\n\n\n=== Action schema ===\n\n{schema}"


SYSTEM_PROMPT = build_system_prompt()


def build_user_message(document_digest: str, user_prompt: str) -> str:
    return (
        "=== Document digest ===\n"
        + document_digest.strip()
        + "\n\n=== User request ===\n"
        + user_prompt.strip()
    )


def build_review_mode_user_message(document_digest: str, user_prompt: str) -> str:
    return (
        "=== Document digest ===\n"
        + document_digest.strip()
        + "\n\n=== User request ===\n"
        + user_prompt.strip()
        + "\n\n=== Review mode (strict) ===\n"
        + "This request is for design review. Prioritize clarity, accessibility, "
        + "print/laser readiness, and SVG hygiene.\n"
        + "Check: overlapping paths, missing strokes on cut lines, text converted to paths, "
        + "consistent units, layer organization, and export readiness.\n"
        + "Reply in plain language unless the user explicitly asks for edits."
    )
