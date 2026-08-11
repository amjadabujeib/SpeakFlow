"""Roleplay evaluation presentation policy shared by finalization paths."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")


def evaluation_availability_note(
    note: str,
    *,
    enough_general: bool,
    enough_grammar: bool,
    evaluation_source: str,
) -> str:
    details = [note]
    if enough_general and not enough_grammar:
        details.append(
            "Grammar is hidden because local correction coverage was insufficient."
        )
    if enough_general and evaluation_source in {
        "deterministic_fallback",
        "disconnect_fallback",
    }:
        details.append(
            "Interaction and vocabulary use local fallback estimates."
        )
    return " ".join(details)


def session_corrections(turns: list[dict]) -> list[dict]:
    """Return only grammar changes backed by a completed grammar evaluation."""
    return [
        {
            "turn_id": item["turn_id"],
            "original": item["user_text"],
            "corrected": item["grammar_corrected_text"],
            "feedback": item.get("grammar_feedback"),
        }
        for item in turns
        if item.get("turn_status", "meaningful") == "meaningful"
        and item.get("grammar_evaluated") is True
        and float(item.get("grammar_error_units") or 0) > 0
        and item.get("grammar_corrected_text")
        and _normalize(item["user_text"])
        != _normalize(item["grammar_corrected_text"])
    ]


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold()))
