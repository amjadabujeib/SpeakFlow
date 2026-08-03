"""Provider error handling and JSON schema helpers for lesson generation."""

from __future__ import annotations

import re

from openai import BadRequestError, RateLimitError

from .curated_lessons import SCORED_TYPES


def _default_activity_phase(
    activities: list, index: int, domain: str
) -> str:
    if domain == "assessment":
        return "independent_check"
    if activities[index].type not in SCORED_TYPES:
        return "learn"
    scored_indexes = [
        position for position, item in enumerate(activities)
        if item.type in SCORED_TYPES
    ]
    return (
        "independent_check"
        if scored_indexes and index == scored_indexes[-1]
        else "guided_practice"
    )


def _clean_source(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:5000]


def _activity_prompt(activity: dict) -> str:
    data = activity["data"]
    question = data.get("question", data)
    return " ".join(str(question.get("prompt", "")).casefold().split())


def _rate_limit_wait_seconds(exc: RateLimitError) -> float:
    """Honor Groq's retry hint without allowing an unbounded worker sleep."""
    raw = exc.response.headers.get("retry-after") if exc.response else None
    try:
        seconds = float(raw) if raw is not None else 3.0
    except (TypeError, ValueError):
        seconds = 3.0
    return min(12.0, max(0.25, seconds + 0.25))


def _provider_retry_after_seconds(exc: RateLimitError) -> int:
    """Return a durable, conservative retry delay from a provider 429."""
    raw = exc.response.headers.get("retry-after") if exc.response else None
    try:
        seconds = float(raw) if raw is not None else 60.0
    except (TypeError, ValueError):
        seconds = 60.0
    return max(1, min(300, int(seconds + 1.0)))


def _openai_error_details(exc: BadRequestError) -> dict:
    """Handle both raw OpenAI-style bodies and SDK-unwrapped error bodies."""
    body = exc.body if isinstance(exc.body, dict) else {}
    nested = body.get("error")
    return nested if isinstance(nested, dict) else body


def _text(min_length: int = 1, max_length: int = 700) -> dict:
    return {"type": "string", "minLength": min_length, "maxLength": max_length}


def _string_list(min_items: int = 1, max_items: int = 6) -> dict:
    return {
        "type": "array",
        "items": _text(1, 300),
        "minItems": min_items,
        "maxItems": max_items,
    }


def _strict_object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _choice_schema() -> dict:
    return _strict_object(
        {
            "id": {"type": "string", "pattern": "^[a-z0-9_-]+$", "maxLength": 40},
            "text": _text(1, 300),
        }
    )


def _question_schema() -> dict:
    return _strict_object(
        {
            "prompt": _text(1, 500),
            "options": {
                "type": "array",
                "items": _choice_schema(),
                "minItems": 3,
                "maxItems": 4,
            },
            "correct_option_id": _text(1, 40),
            "explanation": _text(1, 700),
        }
    )


def _activity_data_schema(activity_type: str) -> dict:
    schemas = {
        "vocabulary_card": _strict_object(
            {
                "word": _text(1, 80),
                "part_of_speech": _text(1, 40),
                "ipa": _text(1, 100),
                "definition": _text(1, 500),
                "examples": _string_list(1, 4),
                "collocations": _string_list(1, 6),
                "native_hint": {"anyOf": [_text(1, 240), {"type": "null"}]},
            }
        ),
        "concept": _strict_object(
            {
                "explanation": _text(1, 1200),
                "key_points": _string_list(1, 6),
                "examples": _string_list(1, 6),
                "native_hint": {"anyOf": [_text(1, 300), {"type": "null"}]},
            }
        ),
        "pronunciation_drill": _strict_object(
            {
                "sound_label": _text(1, 80),
                "ipa": _text(1, 80),
                "instructions": _text(1, 700),
                "tips": _string_list(1, 5),
                "practice_items": _string_list(2, 8),
                "native_hint": {"anyOf": [_text(1, 300), {"type": "null"}]},
            }
        ),
        "multiple_choice": _question_schema(),
        "fill_blank": _strict_object(
            {
                "prompt": _text(1, 500),
                "accepted_answers": _string_list(1, 8),
                "explanation": _text(1, 700),
            }
        ),
        "reading_comprehension": _strict_object(
            {
                "title": _text(1, 160),
                "passage": _text(30, 1800),
                "question": _question_schema(),
                "native_hint": {"anyOf": [_text(1, 300), {"type": "null"}]},
            }
        ),
        "listening_comprehension": _strict_object(
            {
                "title": _text(1, 160),
                "transcript": _text(10, 1000),
                "question": _question_schema(),
                "voice": {"type": "string", "enum": ["american", "british"]},
            }
        ),
        "sentence_order": _strict_object(
            {
                "prompt": _text(1, 300),
                "tokens": {
                    "type": "array",
                    "items": _choice_schema(),
                    "minItems": 3,
                    "maxItems": 12,
                },
                "correct_order": _string_list(3, 12),
                "explanation": _text(1, 700),
            }
        ),
    }
    return schemas[activity_type]


def _lesson_json_schema(
    allowed_types: list[str],
    *,
    blueprint: dict[str, tuple[int, int]] | None = None,
) -> dict:
    return _strict_object(
        {
            "title": _text(1, 160),
            "description": _text(1, 500),
            "intro": _text(1, 700),
            "activities": _strict_object(
                {
                    activity_type: {
                        "type": "array",
                        "items": _activity_data_schema(activity_type),
                        "minItems": (blueprint or {}).get(activity_type, (0, 6))[0],
                        "maxItems": (blueprint or {}).get(activity_type, (0, 6))[1],
                    }
                    for activity_type in allowed_types
                }
            ),
        }
    )
