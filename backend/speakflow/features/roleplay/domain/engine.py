from __future__ import annotations

import difflib
import math
import re
from collections.abc import Iterable
from copy import deepcopy

from speakflow.features.roleplay.domain.catalog import (
    _BUILTIN_BY_ID,
    _OBJECTIVE_EVIDENCE_PATTERNS,
    _WORD,
    BUILTIN_SCENARIOS,
    MIN_SPOKEN_WORDS,
    MIN_TURNS_FOR_EVALUATION,
    MIN_VOICED_SECONDS,
    MIN_WORDS_FOR_LANGUAGE_EVALUATION,
    _objective,
    _rubric,
)
from speakflow.features.roleplay.domain.evaluation import (
    bounded_score,
    eligibility_evaluation_note,
    evaluation_availability_note,
    fallback_interaction_score,
    fallback_vocabulary_score,
    recognition_review_checks,
    trimmed_confidence_mean,
    weighted_delivery_metric,
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
            _objective("respond", "Respond to a relevant question", weight=2),
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
        normalized_evidence = _normalize(evidence)
        if (
            objective_id not in allowed
            or objective_id in seen
            or not evidence
            or not normalized_evidence
            or f" {normalized_evidence} " not in f" {normalized_text} "
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
    if not required:
        # No required objectives: complete when every objective is done.
        all_done = all(
            state.get(item["id"], {}).get("completed") is True for item in objectives
        )
        completed_flag = bool(objectives) and all_done
    else:
        completed_flag = completed_required == len(required)
    return {
        "score": round(100 * completed_weight / max(1, total_weight)),
        "completed": completed_flag,
        "completed_count": completed_required if required else sum(
            1 for item in objectives
            if state.get(item["id"], {}).get("completed") is True
        ),
        "required_count": len(required) if required else len(objectives),
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
    successful = [
        item
        for item in turns
        if item.get("user_text", "").strip()
        and item.get("turn_status", "meaningful") == "meaningful"
    ]
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
    confidence = trimmed_confidence_mean(confidence_values)
    timed_word_count = sum(
        1
        for item in spoken
        for word in item.get("word_feedback", [])
        if isinstance(word, dict)
        and isinstance(word.get("start"), (int, float))
        and isinstance(word.get("end"), (int, float))
    )
    alignment_coverage = (
        min(1.0, round(timed_word_count / spoken_word_count, 3))
        if spoken_word_count
        else None
    )
    raw_fluency = weighted_delivery_metric(spoken, "fluency", "voiced_seconds")
    raw_pitch_variation = weighted_delivery_metric(
        spoken,
        "pitch_variation",
        "voiced_seconds",
    )
    grammar_turns = [
        item for item in successful if item.get("grammar_evaluated") is True
    ]
    grammar_word_count = sum(
        max(0, int(item.get("word_count", 0))) for item in grammar_turns
    )
    grammar_units = sum(
        max(0.0, float(item.get("grammar_error_units", 0)))
        for item in grammar_turns
    )
    grammar_coverage = (
        min(1.0, round(grammar_word_count / word_count, 3))
        if word_count
        else None
    )
    task = objective_progress(scenario, objective_state)
    external = external_evaluation or {}
    interaction = bounded_score(external.get("interaction_score"))
    vocabulary = bounded_score(external.get("vocabulary_score"))
    interaction = (
        interaction
        if interaction is not None
        else fallback_interaction_score(successful)
    )
    vocabulary = (
        vocabulary
        if vocabulary is not None
        else fallback_vocabulary_score(scenario, successful)
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
    enough_grammar = (
        enough_general
        and grammar_word_count >= MIN_WORDS_FOR_LANGUAGE_EVALUATION
        and (grammar_coverage or 0) >= 0.8
    )
    grammar_score = (
        round(100 * math.exp(-4 * grammar_units / grammar_word_count))
        if enough_grammar
        else None
    )
    mode = (
        "spoken"
        if len(spoken) == len(successful) and successful
        else "text"
        if not spoken
        else "mixed"
    )
    review_words = recognition_review_checks(spoken)
    return {
        "scenario": {
            "id": scenario.get("id"),
            "title": scenario.get("title"),
            "icon": scenario.get("icon", "🎭"),
        },
        "mode": mode,
        "eligible": enough_general,
        "eligibility_note": evaluation_availability_note(
            eligibility_evaluation_note(
                mode=mode,
                turns=len(successful),
                word_count=word_count,
                spoken_word_count=spoken_word_count,
                voiced_seconds=voiced_seconds,
                alignment_coverage=alignment_coverage,
                enough_general=enough_general,
                enough_spoken=enough_spoken,
            ),
            enough_general=enough_general,
            enough_grammar=enough_grammar,
            evaluation_source=str(
                external.get("source", "deterministic_fallback")
            ),
        ),
        "scenario_completed": task["completed"],
        "objective_progress": task,
        "scores": {
            "task_achievement": task["score"],
            "interaction": interaction if enough_general else None,
            "grammar_control": grammar_score,
            "vocabulary_function": vocabulary if enough_general else None,
            "delivery_fluency": raw_fluency if enough_spoken else None,
            "intelligibility_proxy": confidence if enough_spoken else None,
            "pitch_variation": raw_pitch_variation if enough_spoken else None,
        },
        "evidence": {
            "successful_turns": len(successful),
            "word_count": word_count,
            "spoken_turns": len(spoken),
            "spoken_word_count": spoken_word_count,
            "voiced_seconds": voiced_seconds,
            "alignment_coverage": alignment_coverage,
            "grammar_error_units": round(grammar_units, 2),
            "grammar_evaluation_coverage": grammar_coverage,
            "delivery_evaluation_eligible": enough_spoken,
            "evaluation_source": external.get("source", "deterministic_fallback"),
            "interaction_evidence": external.get("interaction_evidence", []),
            "vocabulary_evidence": external.get("vocabulary_evidence", []),
            "scenario_evidence": external.get("scenario_evidence", []),
        },
        "recognition_checks": review_words,
    }


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold()))
