"""Connection-binding and public-error policy for roleplay WebSockets."""

from __future__ import annotations

from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
)


class RoleplayTurnInputError(ValueError):
    """A deliberately safe turn error that may be returned to the learner."""


def validate_roleplay_session_binding(
    current_session_id: str | None,
    supplied_session_id: str,
) -> None:
    if current_session_id is not None and current_session_id != supplied_session_id:
        raise PlpConflictError(
            "this connection is already bound to another roleplay session"
        )


def safe_roleplay_turn_error(exc: Exception) -> str:
    if isinstance(
        exc,
        (RoleplayTurnInputError, PlpConflictError, PlpInvalidAttemptError),
    ):
        return str(exc)
    return "The roleplay turn could not be processed."
