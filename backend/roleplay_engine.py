from __future__ import annotations

import difflib
import math
import re
from copy import deepcopy
from typing import Iterable


EVALUATION_VERSION = "roleplay-rubric-v3-2026-07-26"
MIN_TURNS_FOR_EVALUATION = 4
MIN_WORDS_FOR_LANGUAGE_EVALUATION = 30
MIN_SPOKEN_WORDS = 30
MIN_VOICED_SECONDS = 15.0

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

_OBJECTIVE_EVIDENCE_PATTERNS: dict[str, dict[str, tuple[str, ...]]] = {
    "airport_check_in": {
        "destination": (
            r"\b(?:fly|flying|travel|travelling|going)\b.{0,35}\bto\b",
            r"\bdestination\s+(?:is|will be)\b",
        ),
        "identification": (r"\b(?:passport|identification|id)\b",),
        "baggage": (r"\b(?:bag|bags|baggage|luggage|suitcase|suitcases)\b",),
        "seat": (r"\b(?:window|aisle|middle|seat)\b",),
    },
    "hotel_check_in": {
        "reservation": (r"\b(?:reservation|booking|booked|room)\b",),
        "name": (r"\b(?:my name is|under the name|name is)\b",),
        "dates": (r"\b(?:night|nights|staying|until|check out|checkout)\b",),
        "request": (r"\b(?:could i|can i|may i|i would like)\b",),
    },
    "asking_directions": {
        "destination": (r"\b(?:get to|find|go to|looking for)\b",),
        "route": (r"\b(?:how do i|how can i|which way|directions)\b",),
        "clarify": (r"\b(?:repeat|again|do you mean|left or right)\b",),
        "confirm": (r"\b(?:so i|then i|i should)\b",),
    },
    "restaurant_order": {
        "meal": (r"\b(?:i would like|i'll have|i will have|order)\b",),
        "drink": (r"\b(?:drink|water|coffee|tea|juice|soda)\b",),
        "bill": (r"\b(?:bill|check|pay)\b",),
    },
    "cafe_small_talk": {
        "question": (r"\?$",),
        "closing": (r"\b(?:goodbye|see you|nice talking|have a good)\b",),
    },
    "job_interview": {
        "introduction": (r"\b(?:my name is|i am|i'm)\b",),
        "experience": (r"\b(?:experience|worked|work at|work in)\b",),
        "strength": (r"\b(?:strength|good at|skilled|skill)\b",),
        "question": (r"\?$",),
    },
    "business_meeting": {
        "idea": (r"\b(?:i suggest|i propose|my idea|we should)\b",),
        "reason": (r"\b(?:because|reason|so that|in order to)\b",),
        "concern": (r"\b(?:i understand|however|but|concern)\b",),
        "next_step": (r"\b(?:next step|let's|we will|we should now)\b",),
    },
}


def _objective(
    objective_id: str,
    label: str,
    *,
    weight: int = 1,
    required: bool = True,
) -> dict:
    return {
        "id": objective_id,
        "label": label,
        "weight": weight,
        "required": required,
    }


def _rubric(
    rubric_id: str,
    label: str,
    description: str,
    *,
    weight: int = 1,
) -> dict:
    return {
        "id": rubric_id,
        "label": label,
        "description": description,
        "weight": weight,
    }


BUILTIN_SCENARIOS: tuple[dict, ...] = (
    {
        "id": "airport_check_in",
        "version": 1,
        "category": "Travel",
        "icon": "✈️",
        "title": "Airport Check-in",
        "description": "Check in for a flight and obtain your boarding pass.",
        "ai_role": "airline check-in agent",
        "learner_role": "passenger",
        "opening": "Good morning. Welcome to the check-in desk. Where are you flying today?",
        "objectives": [
            _objective("destination", "State your destination", weight=2),
            _objective("identification", "Respond to the identification request"),
            _objective("baggage", "Answer a baggage question"),
            _objective("seat", "Choose or confirm a seat preference"),
        ],
        "target_language": [
            "I am flying to",
            "Here is my passport",
            "I have one bag",
            "I would prefer",
        ],
        "evaluation_rubric": [
            _rubric(
                "travel_information",
                "Travel information",
                "Communicates the requested flight, identity, baggage, and seat details clearly and consistently.",
                weight=2,
            ),
            _rubric(
                "check_in_management",
                "Check-in management",
                "Responds appropriately to the agent and moves the check-in transaction toward completion.",
            ),
        ],
    },
    {
        "id": "hotel_check_in",
        "version": 1,
        "category": "Travel",
        "icon": "🏨",
        "title": "Hotel Check-in",
        "description": "Check into a hotel and confirm the important booking details.",
        "ai_role": "hotel receptionist",
        "learner_role": "guest",
        "opening": "Welcome to the hotel. How may I help you?",
        "objectives": [
            _objective("reservation", "Explain that you have or need a reservation", weight=2),
            _objective("name", "Give the reservation name"),
            _objective("dates", "Confirm the stay dates"),
            _objective("request", "Make one practical room request"),
        ],
        "target_language": [
            "I have a reservation",
            "It is under the name",
            "I am staying until",
            "Could I have",
        ],
        "evaluation_rubric": [
            _rubric(
                "booking_clarity",
                "Booking clarity",
                "Communicates reservation names, dates, and booking details without contradictions.",
                weight=2,
            ),
            _rubric(
                "request_politeness",
                "Practical requests",
                "Makes a clear, appropriately polite hotel request and responds to follow-up questions.",
            ),
        ],
    },
    {
        "id": "asking_directions",
        "version": 1,
        "category": "Travel",
        "icon": "🗺️",
        "title": "Asking for Directions",
        "description": "Ask for directions, clarify the route, and confirm where to go.",
        "ai_role": "helpful local resident",
        "learner_role": "visitor",
        "opening": "Hello. You look a little lost. Can I help you find somewhere?",
        "objectives": [
            _objective("destination", "Say where you want to go", weight=2),
            _objective("route", "Ask how to reach it"),
            _objective("clarify", "Clarify one part of the directions"),
            _objective("confirm", "Confirm the route before leaving"),
        ],
        "target_language": [
            "How can I get to",
            "Do I turn",
            "Could you repeat",
            "So I should",
        ],
        "evaluation_rubric": [
            _rubric(
                "route_clarification",
                "Route clarification",
                "Asks focused questions when a direction or landmark is unclear.",
            ),
            _rubric(
                "route_confirmation",
                "Route confirmation",
                "Accurately restates the essential route before ending the exchange.",
                weight=2,
            ),
        ],
    },
    {
        "id": "restaurant_order",
        "version": 1,
        "category": "Food & Dining",
        "icon": "🍽️",
        "title": "Ordering at a Restaurant",
        "description": "Order a meal, handle a follow-up question, and request the bill.",
        "ai_role": "restaurant server",
        "learner_role": "customer",
        "opening": "Welcome. Are you ready to order, or would you like another minute?",
        "objectives": [
            _objective("meal", "Order a meal", weight=2),
            _objective("drink", "Choose a drink"),
            _objective("follow_up", "Answer a follow-up question about the order"),
            _objective("bill", "Request the bill"),
        ],
        "target_language": [
            "I would like",
            "Could I have",
            "Without",
            "Could we have the bill",
        ],
        "evaluation_rubric": [
            _rubric(
                "order_specificity",
                "Order specificity",
                "Makes the meal and drink order sufficiently specific and handles requested choices.",
                weight=2,
            ),
            _rubric(
                "service_language",
                "Service language",
                "Uses clear, appropriately polite language for requests, changes, and the bill.",
            ),
        ],
    },
    {
        "id": "cafe_small_talk",
        "version": 1,
        "category": "Food & Dining",
        "icon": "☕",
        "title": "Café Small Talk",
        "description": "Start and maintain a friendly short conversation at a café.",
        "ai_role": "friendly café customer",
        "learner_role": "another customer",
        "opening": "Hi. Is anyone sitting here?",
        "objectives": [
            _objective("opening", "Respond naturally to the opening"),
            _objective("topic", "Introduce or develop a small-talk topic", weight=2),
            _objective("question", "Ask a relevant follow-up question"),
            _objective("closing", "Close the conversation politely"),
        ],
        "target_language": [
            "Of course",
            "What do you think about",
            "How about you",
            "It was nice talking to you",
        ],
        "evaluation_rubric": [
            _rubric(
                "reciprocity",
                "Conversational reciprocity",
                "Builds on the partner's responses and balances sharing with relevant questions.",
                weight=2,
            ),
            _rubric(
                "natural_closing",
                "Natural closing",
                "Recognizes an appropriate moment to close and ends the conversation politely.",
            ),
        ],
    },
    {
        "id": "job_interview",
        "version": 1,
        "category": "Business",
        "icon": "💼",
        "title": "Job Interview",
        "description": "Introduce yourself and answer common interview questions with evidence.",
        "ai_role": "job interviewer",
        "learner_role": "candidate",
        "opening": "Thank you for coming today. Could you start by telling me about yourself?",
        "objectives": [
            _objective("introduction", "Give a relevant professional introduction", weight=2),
            _objective("experience", "Describe one useful experience", weight=2),
            _objective("strength", "Explain one strength with an example"),
            _objective("question", "Ask the interviewer one relevant question"),
        ],
        "target_language": [
            "I have experience in",
            "For example",
            "One of my strengths is",
            "Could you tell me more about",
        ],
        "evaluation_rubric": [
            _rubric(
                "professional_relevance",
                "Professional relevance",
                "Keeps answers relevant to the role and presents experience in a professional way.",
            ),
            _rubric(
                "supporting_evidence",
                "Supporting evidence",
                "Supports strengths and experience with concrete, understandable examples.",
                weight=2,
            ),
        ],
    },
    {
        "id": "business_meeting",
        "version": 1,
        "category": "Business",
        "icon": "📊",
        "title": "Business Meeting",
        "description": "Present an idea, respond to a concern, and agree on a next step.",
        "ai_role": "meeting colleague",
        "learner_role": "team member",
        "opening": "Let us begin. What idea would you like the team to consider?",
        "objectives": [
            _objective("idea", "Present a clear idea", weight=2),
            _objective("reason", "Give a reason or supporting detail"),
            _objective("concern", "Respond to a concern or question", weight=2),
            _objective("next_step", "Agree on a concrete next step"),
        ],
        "target_language": [
            "I suggest",
            "The main reason is",
            "I understand your concern",
            "The next step should be",
        ],
        "evaluation_rubric": [
            _rubric(
                "proposal_clarity",
                "Proposal clarity",
                "Presents a focused proposal with a relevant reason or supporting detail.",
                weight=2,
            ),
            _rubric(
                "collaborative_response",
                "Collaborative response",
                "Acknowledges concerns constructively and helps establish a concrete next step.",
            ),
        ],
    },
)

_BUILTIN_BY_ID = {item["id"]: item for item in BUILTIN_SCENARIOS}


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
        "version": 1,
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
        "evaluation_version": EVALUATION_VERSION,
        "scenario": {
            "id": scenario.get("id"),
            "title": scenario.get("title"),
            "icon": scenario.get("icon", "🎭"),
            "version": scenario.get("version", 1),
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
