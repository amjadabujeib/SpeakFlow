"""Atomic cross-worker roleplay turn generation and persistence."""

from __future__ import annotations

import re

from plp.schemas import RoleplayTurnInput
from plp.service import plp_service
from speakflow.features.roleplay.domain.engine import grammar_error_units, objective_progress
from .language import get_grammar_feedback
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
) -> dict:
    """Generate from the latest context and persist before releasing the lease."""
    with plp_service.roleplay_turn_lease(client_session_id):
        context = plp_service.roleplay_context(client_session_id)
        turn_result = _roleplay_turn_reply(context, user_text, turn_id)
        grammar_feedback = get_grammar_feedback(user_text, corrected_text)
        turn_payload = RoleplayTurnInput(
            turn_id=turn_id,
            input_mode=input_mode,
            user_text=user_text,
            assistant_text=turn_result["reply"],
            grammar_corrected_text=corrected_text,
            grammar_feedback=grammar_feedback,
            grammar_error_units=grammar_error_units(user_text, corrected_text),
            word_count=len(
                re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", user_text)
            ),
            word_feedback=word_feedback,
            delivery_metrics=delivery_metrics,
            objective_evidence=turn_result["objective_updates"],
        )
        recorded = plp_service.record_roleplay_turn(
            client_session_id,
            turn_payload,
            objective_updates=turn_result["objective_updates"],
        )
        stored_state = recorded["objective_state"]
        progress = objective_progress(context["scenario"], stored_state)
        return {
            "turn": recorded["turn"],
            "objective_state": stored_state,
            "objective_progress": progress["score"],
            "scenario_complete": progress["completed"],
        }
