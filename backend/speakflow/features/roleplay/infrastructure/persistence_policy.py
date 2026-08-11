"""Validation and persistence-boundary policy for roleplay sessions."""

from __future__ import annotations

import copy
import math

from speakflow.features.learning_plan.engine.schemas import RoleplayTurnInput
from speakflow.features.learning_plan.engine.service_errors import (
    PlpConflictError,
    PlpInvalidAttemptError,
)
from speakflow.features.roleplay.infrastructure.models import RoleplayTurn


def authoritative_roleplay_ended_reason(
    requested: str,
    evaluation: dict,
) -> str:
    if (
        requested == "objective_completed"
        and evaluation.get("scenario_completed") is not True
    ):
        return "learner_ended"
    return requested


def validate_objective_evidence_authority(
    payload: RoleplayTurnInput,
    objective_updates: list[dict],
) -> list[dict]:
    """Require the persisted turn and applied objective updates to agree."""
    submitted = [item.model_dump(mode="json") for item in payload.objective_evidence]
    normalized_updates = [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        for item in objective_updates
    ]
    if submitted != normalized_updates:
        raise PlpInvalidAttemptError(
            "roleplay objective evidence does not match the recorded turn"
        )
    return submitted


def ensure_idempotent_roleplay_turn(
    existing: RoleplayTurn,
    payload: RoleplayTurnInput,
) -> None:
    submitted = payload.model_dump(mode="json")
    stored = {
        "turn_id": existing.turn_id,
        "input_mode": existing.input_mode,
        "user_text": existing.user_text,
        "assistant_text": existing.assistant_text,
        "turn_status": existing.turn_status,
        "grammar_corrected_text": existing.grammar_corrected_text,
        "grammar_feedback": existing.grammar_feedback,
        "grammar_evaluated": existing.grammar_evaluated,
        "grammar_error_units": existing.grammar_error_units,
        "word_count": existing.word_count,
        "word_feedback": copy.deepcopy(existing.word_feedback or []),
        "delivery_metrics": copy.deepcopy(existing.delivery_metrics or {}),
        "objective_evidence": copy.deepcopy(existing.objective_evidence or []),
    }
    if submitted != stored:
        raise PlpConflictError(
            "turn_id was already used for different roleplay content"
        )


def bounded_roleplay_session_metrics(evaluation: dict) -> dict:
    evidence = evaluation.get("evidence", {})
    scores = evaluation.get("scores", {})
    alignment = _bounded_float(evidence.get("alignment_coverage"), 0, 1)
    return {
        "successful_turns": _bounded_int(
            evidence.get("successful_turns"), 0, 500
        ),
        "spoken_word_count": _bounded_int(
            evidence.get("spoken_word_count"), 0, 50000
        ),
        "voiced_seconds": _bounded_float(
            evidence.get("voiced_seconds"), 0, 21600
        )
        or 0.0,
        "alignment_coverage": alignment,
        "average_word_confidence": _bounded_int_or_none(
            scores.get("intelligibility_proxy"), 0, 100
        ),
        "average_fluency": _bounded_int_or_none(
            scores.get("delivery_fluency"), 0, 100
        ),
        "average_prosody": _bounded_int_or_none(
            scores.get("pitch_variation"), 0, 100
        ),
    }


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    bounded = _bounded_float(value, minimum, maximum)
    return round(bounded) if bounded is not None else minimum


def _bounded_int_or_none(
    value: object,
    minimum: int,
    maximum: int,
) -> int | None:
    bounded = _bounded_float(value, minimum, maximum)
    return round(bounded) if bounded is not None else None


def _bounded_float(
    value: object,
    minimum: float,
    maximum: float,
) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return max(minimum, min(maximum, float(value)))
