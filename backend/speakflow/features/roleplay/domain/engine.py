from __future__ import annotations

import difflib
import math
import re
from copy import deepcopy
from typing import Iterable

from speakflow.features.roleplay.domain.catalog import (
    BUILTIN_SCENARIOS,
    MIN_SPOKEN_WORDS,
    MIN_TURNS_FOR_EVALUATION,
    MIN_VOICED_SECONDS,
    MIN_WORDS_FOR_LANGUAGE_EVALUATION,
    _BUILTIN_BY_ID,
    _OBJECTIVE_EVIDENCE_PATTERNS,
    _WORD,
    _objective,
    _rubric,
)


def builtin_scenarios() -> list[dict]:
    return deepcopy(list(BUILTIN_SCENARIOS))


def get_builtin_scenario(scenario_id: str) -> dict | None:
    item = _BUILTIN_BY_ID.get(scenario_id)
    return deepcopy(item) if item is not None else None


def custom_scenario_definition(
    *,
    scenario_id: str,
    category: str,
    title: str,
    description: str,
    designed_cefr_level: str | None = None,
) -> dict:
    clean_title = " ".join(title.split()).strip()
    clean_description = " ".join(description.split()).strip()
    return {
        "id": scenario_id,
        "category": " ".join(category.split()).strip() or "Custom",
        "icon": "🎭",
        "title": clean_title,
        "description": clean_description,
        "ai_role": "a realistic conversation partner in the described situation",
        "learner_role": "the person trying to complete the described task",
        "opening": f"Hello. Let us begin this situation: {clean_description}",
        "objectives": [
            _objective("purpose", "Explain what you need or want", weight=2),
            _objective("details", "Provide at least one relevant detail"),
            _objective("respond", "Respond to two relevant questions", weight=2),
            _objective("outcome", "Confirm a clear outcome or next step"),
        ],
        "target_language": [],
        "evaluation_rubric": [
            _rubric(
                "situational_clarity",
                "Situational clarity",
                "Communicates relevant needs and details clearly within the described situation.",
                weight=2,
            ),
            _rubric(
                "outcome_management",
                "Outcome management",
                "Responds to the partner and works toward a clear result or next step.",
            ),
        ],
        "designed_cefr_level": designed_cefr_level,
    }


def initial_objective_state(scenario: dict) -> dict:
    return {
        item["id"]: {
            "completed": False,
            "evidence_turn_id": None,
            "evidence": None,
        }
        for item in scenario.get("objectives", [])
    }


def validated_objective_updates(
    scenario: dict,
    updates: Iterable[dict],
    *,
    turn_id: str,
    learner_text: str,
) -> list[dict]:
    allowed = {item["id"] for item in scenario.get("objectives", [])}
    normalized_text = _normalize(learner_text)
    result: list[dict] = []
    seen: set[str] = set()
    for item in updates:
        if not isinstance(item, dict):
            continue
        objective_id = str(item.get("objective_id", "")).strip()
        evidence = " ".join(str(item.get("evidence", "")).split()).strip()
        if (
            objective_id not in allowed
            or objective_id in seen
            or not evidence
            or _normalize(evidence) not in normalized_text
        ):
            continue
        seen.add(objective_id)
        result.append(
            {
                "objective_id": objective_id,
                "turn_id": turn_id,
                "evidence": evidence[:240],
            }
        )
    return result


def apply_objective_updates(state: dict, updates: Iterable[dict]) -> dict:
    updated = deepcopy(state)
    for item in updates:
        objective_id = item["objective_id"]
        if objective_id not in updated or updated[objective_id].get("completed"):
            continue
        updated[objective_id] = {
            "completed": True,
            "evidence_turn_id": item["turn_id"],
            "evidence": item["evidence"],
        }
    return updated


def deterministic_objective_updates(
    scenario: dict,
    state: dict,
    *,
    turn_id: str,
    learner_text: str,
) -> list[dict]:
    """Recover explicit objective evidence that the dialogue model omitted.

    These conservative patterns only recognize direct learner statements. They
    complement, rather than replace, contextual model adjudication.
    """
    clean_text = " ".join(learner_text.split()).strip()
    if not clean_text:
        return []
    normalized = clean_text.casefold()
    patterns = _OBJECTIVE_EVIDENCE_PATTERNS.get(str(scenario.get("id")), {})
    updates: list[dict] = []
    for objective in scenario.get("objectives", []):
        objective_id = str(objective.get("id", ""))
        if state.get(objective_id, {}).get("completed") is True:
            continue
        if any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in patterns.get(objective_id, ())
        ):
            updates.append(
                {
                    "objective_id": objective_id,
                    "turn_id": turn_id,
                    "evidence": clean_text[:240],
                }
            )
    return updates


def objective_progress(scenario: dict, state: dict) -> dict:
    objectives = scenario.get("objectives", [])
    total_weight = sum(max(1, int(item.get("weight", 1))) for item in objectives)
    completed_weight = sum(
        max(1, int(item.get("weight", 1)))
        for item in objectives
        if state.get(item["id"], {}).get("completed") is True
    )
    required = [item for item in objectives if item.get("required", True)]
    completed_required = sum(
        1 for item in required if state.get(item["id"], {}).get("completed") is True
    )
    return {
        "score": round(100 * completed_weight / max(1, total_weight)),
        "completed": completed_required == len(required) and bool(required),
        "completed_count": completed_required,
        "required_count": len(required),
    }


def grammar_error_units(original: str, corrected: str | None) -> float:
    if not corrected or _normalize(original) == _normalize(corrected):
        return 0.0
    source = [item.casefold() for item in _WORD.findall(original)]
    target = [item.casefold() for item in _WORD.findall(corrected)]
    matcher = difflib.SequenceMatcher(a=source, b=target, autojunk=False)
    units = 0.0
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        affected = max(a2 - a1, b2 - b1)
        units += max(1, affected)
    return units


def aggregate_session(
    *,
    scenario: dict,
    objective_state: dict,
    turns: list[dict],
    external_evaluation: dict | None = None,
) -> dict:
    successful = [item for item in turns if item.get("user_text", "").strip()]
    spoken = [item for item in successful if item.get("input_mode") == "audio"]
    word_count = sum(max(0, int(item.get("word_count", 0))) for item in successful)
    spoken_word_count = sum(max(0, int(item.get("word_count", 0))) for item in spoken)
    voiced_seconds = round(
        sum(
            max(
                0.0,
                float(item.get("delivery_metrics", {}).get("voiced_seconds") or 0),
            )
            for item in spoken
        ),
        2,
    )
    confidence_values = [
        float(word["score"]) * 100
        for item in spoken
        for word in item.get("word_feedback", [])
        if isinstance(word, dict)
        and isinstance(word.get("score"), (int, float))
        and math.isfinite(float(word["score"]))
        and 0 <= float(word["score"]) <= 1
    ]
    confidence = _trimmed_mean(confidence_values)
    timed_word_count = sum(
        1
        for item in spoken
        for word in item.get("word_feedback", [])
        if isinstance(word, dict)
        and isinstance(word.get("start"), (int, float))
        and isinstance(word.get("end"), (int, float))
    )
    alignment_coverage = (
        round(timed_word_count / spoken_word_count, 3)
        if spoken_word_count
        else None
    )
    fluency = _weighted_metric(spoken, "fluency", "voiced_seconds")
    pitch_variation = _weighted_metric(spoken, "pitch_variation", "voiced_seconds")
    grammar_units = sum(
        max(0.0, float(item.get("grammar_error_units", 0))) for item in successful
    )
    grammar_score = (
        round(100 * math.exp(-4 * grammar_units / word_count))
        if word_count
        else None
    )
    task = objective_progress(scenario, objective_state)
    external = external_evaluation or {}
    interaction = _bounded_score(external.get("interaction_score"))
    vocabulary = _bounded_score(external.get("vocabulary_score"))
    interaction = (
        interaction
        if interaction is not None
        else _fallback_interaction_score(successful)
    )
    vocabulary = (
        vocabulary
        if vocabulary is not None
        else _fallback_vocabulary_score(scenario, successful)
    )
    enough_general = (
        len(successful) >= MIN_TURNS_FOR_EVALUATION
        and word_count >= MIN_WORDS_FOR_LANGUAGE_EVALUATION
    )
    enough_spoken = (
        len(spoken) >= MIN_TURNS_FOR_EVALUATION
        and spoken_word_count >= MIN_SPOKEN_WORDS
        and voiced_seconds >= MIN_VOICED_SECONDS
        and (alignment_coverage or 0) >= 0.7
    )
    mode = (
        "spoken"
        if len(spoken) == len(successful) and successful
        else "text"
        if not spoken
        else "mixed"
    )
    review_words = _recognition_checks(spoken)
    return {
        "scenario": {
            "id": scenario.get("id"),
            "title": scenario.get("title"),
            "icon": scenario.get("icon", "🎭"),
        },
        "mode": mode,
        "eligible": enough_spoken if mode != "text" else enough_general,
        "eligibility_note": _eligibility_note(
            mode=mode,
            turns=len(successful),
            word_count=word_count,
            spoken_word_count=spoken_word_count,
            voiced_seconds=voiced_seconds,
            alignment_coverage=alignment_coverage,
        ),
        "scenario_completed": task["completed"],
        "objective_progress": task,
        "scores": {
            "task_achievement": task["score"],
            "interaction": interaction,
            "grammar_control": grammar_score,
            "vocabulary_function": vocabulary,
            "delivery_fluency": fluency,
            "intelligibility_proxy": confidence,
            "pitch_variation": pitch_variation,
        },
        "evidence": {
            "successful_turns": len(successful),
            "word_count": word_count,
            "spoken_turns": len(spoken),
            "spoken_word_count": spoken_word_count,
            "voiced_seconds": voiced_seconds,
            "alignment_coverage": alignment_coverage,
            "grammar_error_units": round(grammar_units, 2),
            "evaluation_source": external.get("source", "deterministic_fallback"),
            "interaction_evidence": external.get("interaction_evidence", []),
            "vocabulary_evidence": external.get("vocabulary_evidence", []),
            "scenario_evidence": external.get("scenario_evidence", []),
        },
        "recognition_checks": review_words,
    }


def _fallback_interaction_score(turns: list[dict]) -> int | None:
    if not turns:
        return None
    count_score = min(100, 35 + 13 * len(turns))
    substantive = sum(1 for item in turns if item.get("word_count", 0) >= 4)
    return round(0.6 * count_score + 0.4 * min(100, 25 * substantive))


def _fallback_vocabulary_score(scenario: dict, turns: list[dict]) -> int | None:
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


def _weighted_metric(turns: list[dict], metric: str, weight: str) -> int | None:
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
    return round(sum(value * weight for value, weight in values) / sum(weight for _, weight in values))


def _trimmed_mean(values: list[float]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    trim = int(len(ordered) * 0.1) if len(ordered) >= 10 else 0
    kept = ordered[trim : len(ordered) - trim] if trim else ordered
    return round(sum(kept) / len(kept))


def _recognition_checks(turns: list[dict]) -> list[dict]:
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


def _eligibility_note(
    *,
    mode: str,
    turns: int,
    word_count: int,
    spoken_word_count: int,
    voiced_seconds: float,
    alignment_coverage: float | None,
) -> str:
    if mode == "text":
        if turns >= MIN_TURNS_FOR_EVALUATION and word_count >= MIN_WORDS_FOR_LANGUAGE_EVALUATION:
            return "Enough text evidence for a practice evaluation."
        return (
            f"Use at least {MIN_TURNS_FOR_EVALUATION} turns and "
            f"{MIN_WORDS_FOR_LANGUAGE_EVALUATION} words for a reliable text evaluation."
        )
    if (
        turns >= MIN_TURNS_FOR_EVALUATION
        and spoken_word_count >= MIN_SPOKEN_WORDS
        and voiced_seconds >= MIN_VOICED_SECONDS
        and (alignment_coverage or 0) >= 0.7
    ):
        return "Enough spoken evidence for a practice evaluation."
    return (
        f"Use at least {MIN_TURNS_FOR_EVALUATION} spoken turns, "
        f"{MIN_SPOKEN_WORDS} recognized words, and {int(MIN_VOICED_SECONDS)} "
        "seconds of clear speech for a reliable spoken evaluation."
    )


def _bounded_score(value: object) -> int | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return max(0, min(100, round(float(value))))


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold()))
