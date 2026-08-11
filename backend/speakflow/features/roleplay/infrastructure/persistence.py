"""Roleplay scenario, session, turn, and transcript persistence behavior."""

from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from datetime import UTC

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from speakflow.features.learning_plan.engine.database import get_engine, session_scope
from speakflow.features.learning_plan.engine.identity import (
    current_user_id as _user_id,
)
from speakflow.features.learning_plan.engine.models import (
    LearnerProfile,
)
from speakflow.features.learning_plan.engine.schemas import (
    RoleplayScenarioView,
    RoleplaySessionStart,
    RoleplaySessionStartView,
    RoleplaySessionView,
    RoleplayTranscriptView,
    RoleplayTurnInput,
)
from speakflow.features.learning_plan.engine.service_errors import (
    PlpConflictError,
    PlpNotFoundError,
)
from speakflow.features.learning_plan.engine.service_identity import (
    _database_error,
    _ensure_local_user,
)
from speakflow.features.learning_plan.engine.service_progress import (
    _roleplay_session_view,
    _roleplay_turn_dict,
)
from speakflow.features.roleplay.domain.engine import (
    apply_objective_updates,
    get_builtin_scenario,
    initial_objective_state,
)
from speakflow.features.roleplay.infrastructure.models import (
    RoleplayScenario,
    RoleplaySession,
    RoleplayTurn,
)
from speakflow.shared.orm import utc_now

from .persistence_policy import (
    authoritative_roleplay_ended_reason,
    bounded_roleplay_session_metrics,
    ensure_idempotent_roleplay_turn,
    validate_objective_evidence_authority,
)
from .scenario_repository import PlpRoleplayScenarioMixin


class PlpRoleplayMixin(PlpRoleplayScenarioMixin):
    @contextmanager
    def roleplay_turn_lease(self, client_session_id: str):
        """Serialize context-generation-record cycles across backend workers."""
        lock_identity = f"{_user_id()}:{client_session_id}"
        digest = hashlib.blake2b(
            lock_identity.encode("utf-8"),
            digest_size=8,
            person=b"roleplay",
        ).digest()
        lock_key = int.from_bytes(digest, byteorder="big", signed=True)
        with get_engine().connect() as connection:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            )
            try:
                yield
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                )

    def start_roleplay_session(
        self, payload: RoleplaySessionStart
    ) -> RoleplaySessionStartView:
        try:
            with session_scope() as session:
                _ensure_local_user(session)
                existing = session.scalar(
                    select(RoleplaySession).where(
                        RoleplaySession.client_session_id == payload.client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                )
                profile = session.get(LearnerProfile, _user_id())
                level = profile.cefr_level if profile is not None else "B1"
                if existing is not None:
                    if existing.status != "active":
                        raise PlpConflictError("this roleplay session has already ended")
                    if existing.scenario_id != payload.scenario_id:
                        raise PlpConflictError(
                            "client_session_id was already used for another scenario"
                        )
                    scenario = copy.deepcopy(existing.scenario_snapshot)
                else:
                    scenario = get_builtin_scenario(payload.scenario_id)
                    if scenario is None:
                        custom = session.get(RoleplayScenario, payload.scenario_id)
                        if custom is None or custom.user_id != _user_id():
                            raise PlpNotFoundError("roleplay scenario was not found")
                        scenario = copy.deepcopy(custom.definition)
                    existing = RoleplaySession(
                        user_id=_user_id(),
                        client_session_id=payload.client_session_id,
                        scenario_id=scenario["id"],
                        cefr_level=level,
                        scenario=scenario["title"],
                        scenario_snapshot=scenario,
                        status="active",
                        objective_state=initial_objective_state(scenario),
                        duration_seconds=0,
                        message_count=0,
                        successful_turns=0,
                        spoken_word_count=0,
                        voiced_seconds=0,
                        review_words=[],
                        evaluation={},
                    )
                    session.add(existing)
                    session.flush()
                level = existing.cefr_level
                return RoleplaySessionStartView(
                    client_session_id=existing.client_session_id,
                    status="active",
                    scenario=RoleplayScenarioView.model_validate(
                        {
                            **scenario,
                            "custom": str(scenario["id"]).startswith("custom_"),
                        }
                    ),
                    objective_state=copy.deepcopy(existing.objective_state),
                    cefr_level=level,
                )
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def roleplay_context(self, client_session_id: str) -> dict:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession).where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                turns = session.scalars(
                    select(RoleplayTurn)
                    .where(RoleplayTurn.session_id == row.id)
                    .order_by(RoleplayTurn.sequence)
                ).all()
                return {
                    "session_id": row.id,
                    "client_session_id": row.client_session_id,
                    "status": row.status,
                    "scenario": copy.deepcopy(row.scenario_snapshot),
                    "objective_state": copy.deepcopy(row.objective_state),
                    "cefr_level": row.cefr_level,
                    "turns": [_roleplay_turn_dict(item) for item in turns],
                    "created_at": row.created_at,
                }
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def record_roleplay_turn(
        self,
        client_session_id: str,
        payload: RoleplayTurnInput,
        *,
        objective_updates: list[dict],
    ) -> dict:
        try:
            validated_updates = validate_objective_evidence_authority(
                payload,
                objective_updates,
            )
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession)
                    .where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                    .with_for_update()
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                if row.status != "active":
                    raise PlpConflictError("roleplay session is no longer active")
                existing = session.scalar(
                    select(RoleplayTurn).where(
                        RoleplayTurn.session_id == row.id,
                        RoleplayTurn.turn_id == payload.turn_id,
                    )
                )
                if existing is not None:
                    ensure_idempotent_roleplay_turn(existing, payload)
                    return {
                        "turn": _roleplay_turn_dict(existing),
                        "objective_state": copy.deepcopy(row.objective_state),
                    }
                sequence = (
                    session.scalar(
                        select(func.max(RoleplayTurn.sequence)).where(
                            RoleplayTurn.session_id == row.id
                        )
                    )
                    or 0
                ) + 1
                if sequence > 500:
                    raise PlpConflictError("roleplay turn limit reached")
                turn = RoleplayTurn(
                    session_id=row.id,
                    sequence=sequence,
                    **payload.model_dump(),
                )
                session.add(turn)
                row.message_count = sequence
                if payload.turn_status == "meaningful":
                    row.successful_turns = min(500, row.successful_turns + 1)
                row.objective_state = apply_objective_updates(
                    row.objective_state,
                    validated_updates,
                )
                session.flush()
                return {
                    "turn": _roleplay_turn_dict(turn),
                    "objective_state": copy.deepcopy(row.objective_state),
                }
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def complete_roleplay_session(
        self,
        client_session_id: str,
        *,
        ended_reason: str,
        evaluation: dict,
        corrections: list[dict],
    ) -> RoleplaySessionView:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession)
                    .where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                    .with_for_update()
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                if row.status in {"complete", "abandoned"}:
                    return _roleplay_session_view(row)
                now = utc_now()
                metrics = bounded_roleplay_session_metrics(evaluation)
                successful_turns = metrics["successful_turns"]
                row.status = "complete" if successful_turns > 0 else "abandoned"
                row.ended_reason = authoritative_roleplay_ended_reason(
                    ended_reason,
                    evaluation,
                )
                row.ended_at = now
                started = row.created_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                row.duration_seconds = max(
                    0, min(21600, int((now - started).total_seconds()))
                )
                row.evaluation = {
                    **copy.deepcopy(evaluation),
                    "corrections": copy.deepcopy(corrections),
                }
                row.successful_turns = successful_turns
                row.spoken_word_count = metrics["spoken_word_count"]
                row.voiced_seconds = metrics["voiced_seconds"]
                row.alignment_coverage = metrics["alignment_coverage"]
                row.average_word_confidence = metrics["average_word_confidence"]
                row.average_fluency = metrics["average_fluency"]
                row.average_prosody = metrics["average_prosody"]
                row.review_words = [
                    {
                        "word": item["word"],
                        "confidence": item["confidence"],
                    }
                    for item in evaluation.get("recognition_checks", [])
                ]
                session.flush()
                return _roleplay_session_view(row)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def begin_roleplay_finalization(self, client_session_id: str) -> bool:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession)
                    .where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                    .with_for_update()
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                if row.status in {"complete", "abandoned"}:
                    return False
                # Finalization always runs under the session advisory lease. A
                # persisted finalizing state here therefore belongs to a worker
                # that crashed and released its database connection.
                row.status = "finalizing"
                return True
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def release_roleplay_finalization(self, client_session_id: str) -> None:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession)
                    .where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                    .with_for_update()
                )
                if row is not None and row.status == "finalizing":
                    row.status = "active"
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def list_roleplay_sessions(
        self, limit: int = 50
    ) -> list[RoleplaySessionView]:
        try:
            with session_scope() as session:
                rows = session.scalars(
                    select(RoleplaySession)
                    .where(RoleplaySession.user_id == _user_id())
                    .order_by(RoleplaySession.created_at.desc())
                    .limit(limit)
                ).all()
                return [_roleplay_session_view(row) for row in rows]
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_roleplay_session(
        self, client_session_id: str
    ) -> RoleplaySessionView:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession).where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                return _roleplay_session_view(row)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_roleplay_transcript(
        self, client_session_id: str
    ) -> RoleplayTranscriptView:
        try:
            with session_scope() as session:
                row = session.scalar(
                    select(RoleplaySession).where(
                        RoleplaySession.client_session_id == client_session_id,
                        RoleplaySession.user_id == _user_id(),
                    )
                )
                if row is None:
                    raise PlpNotFoundError("roleplay session was not found")
                turns = session.scalars(
                    select(RoleplayTurn)
                    .where(RoleplayTurn.session_id == row.id)
                    .order_by(RoleplayTurn.sequence)
                ).all()
                scenario = copy.deepcopy(row.scenario_snapshot)
                return RoleplayTranscriptView.model_validate(
                    {
                        "read_only": True,
                        "session": _roleplay_session_view(row),
                        "scenario": {
                            **scenario,
                            "custom": str(scenario.get("id", "")).startswith(
                                "custom_"
                            ),
                        },
                        "turns": [
                            {
                                "turn_id": turn.turn_id,
                                "sequence": turn.sequence,
                                "input_mode": turn.input_mode,
                                "user_text": turn.user_text,
                                "assistant_text": turn.assistant_text,
                                "turn_status": turn.turn_status,
                                "grammar_corrected_text": (
                                    turn.grammar_corrected_text
                                ),
                                "grammar_feedback": turn.grammar_feedback,
                                "word_confidence": copy.deepcopy(
                                    turn.word_feedback or []
                                ),
                                "created_at": turn.created_at,
                            }
                            for turn in turns
                        ],
                    }
                )
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
