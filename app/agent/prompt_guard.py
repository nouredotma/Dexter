from __future__ import annotations

import re

from app.config import get_settings

_SUSPICIOUS_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"reveal\s+(system|developer)\s+prompt",
    r"print\s+all\s+secrets",
    r"bypass\s+safety",
]


def _contains_suspicious_content(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _SUSPICIOUS_PATTERNS)


def validate_user_prompt(prompt: str) -> tuple[bool, str | None]:
    settings = get_settings()
    max_chars = int(settings.max_prompt_chars)
    if len(prompt) > max_chars:
        return False, f"Prompt exceeds maximum length ({max_chars} chars)"
    if _contains_suspicious_content(prompt):
        return False, "Prompt appears to contain prompt-injection patterns"
    return True, None


def validate_tool_input(tool_name: str, tool_input: dict) -> tuple[bool, str | None]:
    settings = get_settings()
    max_chars = int(settings.max_tool_input_chars)
    for key, value in tool_input.items():
        if isinstance(value, str):
            if len(value) > max_chars:
                return False, f"Tool input too long for '{key}' ({max_chars} char max)"
            if _contains_suspicious_content(value):
                return False, f"Tool input blocked by injection guard for {tool_name}"
    return True, None
