"""Roleplay evaluation presentation policy shared by finalization paths."""

from __future__ import annotations

import math
import re

from speakflow.features.roleplay.domain.catalog import (
    MIN_SPOKEN_WORDS,
    MIN_TURNS_FOR_EVALUATION,
    MIN_VOICED_SECONDS,
    MIN_WORDS_FOR_LANGUAGE_EVALUATION,
)

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


def fallback_interaction_score(turns: list[dict]) -> int | None:
    if not turns:
        return None
    count_score = min(100, 35 + 13 * len(turns))
    substantive = sum(1 for item in turns if item.get("word_count", 0) >= 4)
    return round(0.6 * count_score + 0.4 * min(100, 25 * substantive))


def fallback_vocabulary_score(scenario: dict, turns: list[dict]) -> int | None:
    if not turns:
        return None
    text = _normalize(" ".join(item.get("user_text", "") for item in turns))
    targets = [
        _normalize(item)
        for item in scenario.get("target_language", [])
        if _normalize(item)
    ]
    coverage = (
        sum(1 for item in targets if item in text) / len(targets)
        if targets
        else 0
    )
    words = [item.casefold() for item in _WORD.findall(text)]
    diversity = len(set(words)) / max(1, len(words))
    return round(min(100, 45 + 35 * coverage + 20 * min(1.0, diversity / 0.65)))


def weighted_delivery_metric(turns: list[dict], metric: str, weight: str) -> int | None:
    values: list[tuple[float, float]] = []
    for item in turns:
        metrics = item.get("delivery_metrics", {})
        value = metrics.get(metric)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            continue
        item_weight = metrics.get(weight)
        safe_weight = (
            float(item_weight)
            if isinstance(item_weight, (int, float))
            and math.isfinite(float(item_weight))
            and float(item_weight) > 0
            else 1.0
        )
        values.append((float(value), safe_weight))
    if not values:
        return None
    weighted = sum(value * weight for value, weight in values) / sum(
        weight for _, weight in values
    )
    return max(0, min(100, round(weighted)))


def trimmed_confidence_mean(values: list[float]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    trim = int(len(ordered) * 0.1) if len(ordered) >= 10 else 0
    kept = ordered[trim : len(ordered) - trim] if trim else ordered
    return round(sum(kept) / len(kept))


def recognition_review_checks(turns: list[dict]) -> list[dict]:
    weakest: dict[str, dict] = {}
    for turn in turns:
        for word in turn.get("word_feedback", []):
            if not isinstance(word, dict):
                continue
            value = str(word.get("word", "")).strip()
            score = word.get("score")
            if (
                not value
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or float(score) < 0
                or float(score) >= 0.8
            ):
                continue
            key = value.casefold()
            candidate = {
                "word": value,
                "confidence": round(float(score) * 100),
                "reason": "recognizer_uncertain",
            }
            if key not in weakest or candidate["confidence"] < weakest[key]["confidence"]:
                weakest[key] = candidate
    return sorted(weakest.values(), key=lambda item: item["confidence"])[:20]


def eligibility_evaluation_note(
    *,
    mode: str,
    turns: int,
    word_count: int,
    spoken_word_count: int,
    voiced_seconds: float,
    alignment_coverage: float | None,
    enough_general: bool,
    enough_spoken: bool,
) -> str:
    if not enough_general:
        return (
            f"Use at least {MIN_TURNS_FOR_EVALUATION} turns and "
            f"{MIN_WORDS_FOR_LANGUAGE_EVALUATION} words for reliable language scores."
        )
    if mode == "text":
        return "Enough text evidence for reliable practice scores."
    if enough_spoken:
        return "Enough conversation and spoken evidence for reliable practice scores."
    return (
        "Language scores have enough evidence. Speaking-delivery scores remain hidden "
        f"until there are at least {MIN_TURNS_FOR_EVALUATION} spoken turns, "
        f"{MIN_SPOKEN_WORDS} recognized words, {int(MIN_VOICED_SECONDS)} seconds "
        "of clear speech, and sufficient word alignment."
    )


def bounded_score(value: object) -> int | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return max(0, min(100, round(float(value))))


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold()))
