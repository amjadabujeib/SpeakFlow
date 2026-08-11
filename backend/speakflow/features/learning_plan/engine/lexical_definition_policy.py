"""Low-level validation for learner-facing lexical definitions."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+(?:['’][a-z0-9]+)?", re.IGNORECASE)
_MEANING_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "used",
        "which",
        "with",
    }
)


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold().replace("’", "'")))


def contains_phrase(value: str, phrase: str) -> bool:
    needle = _normalize(phrase).split()
    haystack = _normalize(value).split()
    return bool(needle) and any(
        haystack[index : index + len(needle)] == needle
        for index in range(len(haystack) - len(needle) + 1)
    )


def _meaning_tokens(value: str) -> set[str]:
    result: set[str] = set()
    for token in _normalize(value).split():
        if token in _MEANING_STOPWORDS or len(token) < 4:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[: -len(suffix)]
                break
        result.add(token)
    return result


def validate_learner_definition(
    value: str,
    *,
    target: str,
    source_definition: str,
    maximum_words: int,
    request_id: str,
) -> str:
    definition = " ".join(value.split()).strip().rstrip(".;:").strip()
    words = _WORD.findall(definition)
    if len(words) < 3 or len(words) > maximum_words:
        raise ValueError(
            f"{request_id} learner definition must contain 3-{maximum_words} words"
        )
    if contains_phrase(definition, target):
        raise ValueError(f"{request_id} learner definition is circular")
    sentences = [
        item.strip() for item in re.split(r"(?<=[.!?])\s+", definition) if item.strip()
    ]
    if len(sentences) != 1 or "\n" in definition or "\r" in definition:
        raise ValueError(f"{request_id} learner definition must be one sentence")
    if not (_meaning_tokens(definition) & _meaning_tokens(source_definition)):
        raise ValueError(
            f"{request_id} learner definition has no lexical anchor to its source meaning"
        )
    return definition


def optional_learner_definition(
    value: str,
    *,
    target: str,
    source_definition: str,
    maximum_words: int,
    request_id: str,
) -> str | None:
    """Return a validated definition, or ``None`` for a safe fallback path."""

    try:
        return validate_learner_definition(
            value,
            target=target,
            source_definition=source_definition,
            maximum_words=maximum_words,
            request_id=request_id,
        )
    except ValueError:
        return None
