"""Groq credential discovery shared by runtime and PLP providers."""

from __future__ import annotations

import os


def configured_groq_api_keys() -> tuple[str, ...]:
    """Return configured keys in stable order without ever exposing them.

    ``GROQ_API_KEYS`` accepts one or more comma-separated credentials. Duplicate
    entries are removed so one credential is never selected twice.
    """

    candidates = os.environ.get("GROQ_API_KEYS", "").split(",")

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return tuple(result)
