"""Atomic cross-worker roleplay turn generation and persistence."""

from __future__ import annotations

import re

from speakflow.features.language_tools.infrastructure.language import (
    get_grammar_feedback,
)
from speakflow.features.learning_plan.engine.schemas import (
    RoleplayDeliveryMetrics,
    RoleplayTurnInput,
)
from speakflow.features.learning_plan.engine.service import PlpConflictError
from speakflow.features.roleplay.application.service import roleplay_service
from speakflow.features.roleplay.domain.engine import (
    grammar_error_units,
    objective_progress,
)
from speakflow.features.roleplay.domain.turn_policy import (
    ensure_typed_roleplay_turn_is_english,
)

from .roleplay_scenario import _roleplay_turn_reply


def process_roleplay_turn(
    *,
    client_session_id: str,
    turn_id: str,
    input_mode: str,
    user_text: str,
    corrected_text: str | None,
    word_feedback: list[dict],
    delivery_metrics: dict,
    grammar_evaluated: bool,
) -> dict:
    """Generate from the latest context and persist before releasing the lease."""
    if input_mode == "text":
        ensure_typed_roleplay_turn_is_english(user_text)
    with roleplay_service.turn_lease(client_session_id):
        context = roleplay_service.context(client_session_id)
        if context.get("status", "active") != "active":
            raise PlpConflictError("roleplay session is no longer active")
        grammar_feedback = get_grammar_feedback(user_text, corrected_text)
        base_payload = {
            "turn_id": turn_id,
            "input_mode": input_mode,
            "user_text": user_text,
            "grammar_corrected_text": corrected_text,
            "grammar_feedback": grammar_feedback,
            "grammar_evaluated": grammar_evaluated,
            "grammar_error_units": grammar_error_units(user_text, corrected_text),
            "word_count": len(
                re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", user_text)
            ),
            "word_feedback": word_feedback,
            "delivery_metrics": delivery_metrics,
        }
        existing = next(
            (
                item
                for item in context["turns"]
                if item.get("turn_id") == turn_id
            ),
            None,
        )
        if existing is not None:
            if existing.get("turn_status", "meaningful") != "meaningful":
                _clear_roleplay_evaluation_evidence(base_payload)
            probe = RoleplayTurnInput(
                **base_payload,
                assistant_text="Previously generated response.",
            ).model_dump(mode="json")
            existing = {
                **existing,
                "delivery_metrics": RoleplayDeliveryMetrics.model_validate(
                    existing.get("delivery_metrics") or {}
                ).model_dump(mode="json"),
            }
            replay_fields = (
                ("turn_id", "input_mode", "user_text")
                if input_mode == "text"
                else tuple(base_payload)
            )
            if any(existing.get(field) != probe[field] for field in replay_fields):
                raise PlpConflictError(
                    "turn_id was already used for different roleplay input"
                )
            return _turn_result(context, existing, context["objective_state"])

        turn_result = _roleplay_turn_reply(context, user_text, turn_id)
        turn_status = turn_result["turn_status"]
        base_payload["turn_status"] = turn_status
        if turn_status != "meaningful":
            _clear_roleplay_evaluation_evidence(base_payload)
        turn_payload = RoleplayTurnInput(
            **base_payload,
            assistant_text=turn_result["reply"],
            objective_evidence=turn_result["objective_updates"],
        )
        recorded = roleplay_service.record_turn(
            client_session_id,
            turn_payload,
            objective_updates=turn_result["objective_updates"],
        )
        stored_state = recorded["objective_state"]
        return _turn_result(context, recorded["turn"], stored_state)


def _turn_result(context: dict, turn: dict, objective_state: dict) -> dict:
    progress = objective_progress(context["scenario"], objective_state)
    return {
        "turn": turn,
        "turn_status": turn.get("turn_status", "meaningful"),
        "objective_state": objective_state,
        "objective_progress": progress["score"],
        "scenario_complete": progress["completed"],
    }


def _clear_roleplay_evaluation_evidence(payload: dict) -> None:
    """Canonicalize a nonmeaningful turn for storage and safe replay checks."""

    payload.update(
        grammar_corrected_text=None,
        grammar_feedback=None,
        grammar_evaluated=False,
        grammar_error_units=0.0,
        word_count=0,
        word_feedback=[],
        delivery_metrics={},
    )
