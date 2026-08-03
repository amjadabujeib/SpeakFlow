"""Explicit roleplay-session finalization endpoint."""

from __future__ import annotations

import asyncio

from plp.schemas import RoleplayFinalizeInput, RoleplayFinalizeView
from plp.service import plp_service
from speakflow.features.roleplay.domain.engine import aggregate_session
from .roleplay_evaluation import (
    _roleplay_external_evaluation,
    _roleplay_http_error,
)


async def finalize_roleplay_session(
    client_session_id: str,
    payload: RoleplayFinalizeInput,
) -> RoleplayFinalizeView:
    claimed = False
    try:
        claimed = await asyncio.to_thread(
            plp_service.begin_roleplay_finalization,
            client_session_id,
        )
        if not claimed:
            session = await asyncio.to_thread(
                plp_service.get_roleplay_session, client_session_id
            )
            return RoleplayFinalizeView(
                session=session,
                corrections=session.evaluation.get("corrections", []),
            )
        context = await asyncio.to_thread(
            plp_service.roleplay_context, client_session_id
        )
        external = await asyncio.to_thread(
            _roleplay_external_evaluation, context
        )
        evaluation = aggregate_session(
            scenario=context["scenario"],
            objective_state=context["objective_state"],
            turns=context["turns"],
            external_evaluation=external,
        )
        corrections = [
            {
                "turn_id": item["turn_id"],
                "original": item["user_text"],
                "corrected": item["grammar_corrected_text"],
                "feedback": item["grammar_feedback"],
            }
            for item in context["turns"]
            if item.get("grammar_corrected_text")
        ]
        session = await asyncio.to_thread(
            plp_service.complete_roleplay_session,
            client_session_id,
            ended_reason=payload.ended_reason,
            evaluation=evaluation,
            corrections=corrections,
        )
        return RoleplayFinalizeView(session=session, corrections=corrections)
    except Exception as exc:
        if claimed:
            try:
                await asyncio.to_thread(
                    plp_service.release_roleplay_finalization,
                    client_session_id,
                )
            except Exception:
                pass
        raise _roleplay_http_error(exc) from exc
