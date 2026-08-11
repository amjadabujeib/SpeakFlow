"""Explicit roleplay-session finalization endpoint."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Path

from speakflow.features.learning_plan.engine.schemas import (
    RoleplayFinalizeInput,
    RoleplayFinalizeView,
)
from speakflow.features.roleplay.application.service import roleplay_service
from speakflow.features.roleplay.domain.engine import aggregate_session
from speakflow.features.roleplay.domain.evaluation import session_corrections

from .evaluation import (
    _roleplay_external_evaluation,
    _roleplay_http_error,
)


async def finalize_roleplay_session(
    client_session_id: Annotated[
        str,
        Path(pattern=r"^[a-zA-Z0-9_\-]{8,80}$"),
    ],
    payload: RoleplayFinalizeInput,
) -> RoleplayFinalizeView:
    try:
        return await asyncio.to_thread(
            _finalize_roleplay_session,
            client_session_id,
            payload.ended_reason,
        )
    except Exception as exc:
        raise _roleplay_http_error(exc) from exc


def _finalize_roleplay_session(
    client_session_id: str,
    ended_reason: str,
) -> RoleplayFinalizeView:
    claimed = False
    with roleplay_service.turn_lease(client_session_id):
        try:
            claimed = roleplay_service.begin_finalization(client_session_id)
            if not claimed:
                session = roleplay_service.session(client_session_id)
                return RoleplayFinalizeView(
                    session=session,
                    corrections=session.evaluation.get("corrections", []),
                )
            context = roleplay_service.context(client_session_id)
            external = _roleplay_external_evaluation(context)
            evaluation = aggregate_session(
                scenario=context["scenario"],
                objective_state=context["objective_state"],
                turns=context["turns"],
                external_evaluation=external,
            )
            corrections = session_corrections(context["turns"])
            session = roleplay_service.complete_session(
                client_session_id,
                ended_reason=ended_reason,
                evaluation=evaluation,
                corrections=corrections,
            )
            return RoleplayFinalizeView(session=session, corrections=corrections)
        except Exception:
            if claimed:
                try:
                    roleplay_service.release_finalization(client_session_id)
                except Exception:
                    pass
            raise
