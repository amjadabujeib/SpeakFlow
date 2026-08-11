"""Lifecycle, health, and learner-profile service behavior."""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from speakflow.features.roleplay.infrastructure.models import (
    RoleplayScenario,
    RoleplaySession,
)

from .curriculum_readiness import assess_curriculum, reviewed_source_is_current
from .database import check_database, session_scope
from .generator import LessonGenerator
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt,
    CurriculumChunk,
    CurriculumSource,
    GenerationJob,
    LearnerProfile,
    LearningPlan,
    LessonProgress,
    Skill,
    SkillEvidence,
    StudyDay,
    utc_now,
)
from .retrieval import CurriculumRetriever
from .schemas import LearnerProfileInput, LearnerProfileView
from .seed import SOURCE
from .service_errors import JOB_HEARTBEAT_SECONDS, PlpNotFoundError
from .service_identity import _database_error, _ensure_local_user, _profile_view
from .weekly_mission import WeeklyMissionGenerator


class PlpServiceBaseMixin:
    def __init__(self) -> None:
        self.retriever = CurriculumRetriever()
        self.generator = LessonGenerator()
        self.weekly_generator = WeeklyMissionGenerator(self.generator)
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_worker(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._expire_stale_roleplay_sessions()
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="plp-generation-worker", daemon=True
        )
        self._worker_thread.start()

    @staticmethod
    def _reviewed_curriculum_is_current() -> bool:
        try:
            with session_scope() as session:
                source = session.get(CurriculumSource, SOURCE["id"])
                return reviewed_source_is_current(
                    source.checksum if source is not None else None
                )
        except SQLAlchemyError as exc:
            print(f"Could not verify reviewed curriculum version: {exc}")
            return False

    @staticmethod
    def _expire_stale_roleplay_sessions() -> None:
        """Close sessions left active by a prior process or failed socket bind."""
        now = utc_now()
        try:
            with session_scope() as session:
                session.execute(
                    update(RoleplaySession)
                    .where(
                        RoleplaySession.status == "active",
                        RoleplaySession.created_at <= now - timedelta(hours=6),
                    )
                    .values(
                        status="abandoned",
                        ended_reason="timeout",
                        ended_at=now,
                    )
                )
        except SQLAlchemyError as exc:
            print(f"Could not expire stale roleplay sessions: {exc}")

    def stop_worker(self) -> bool:
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
            return not self._worker_thread.is_alive()
        return True

    def close(self) -> None:
        self.retriever.close()
        self.generator.close()

    @contextmanager
    def _job_lease(self, job_id: uuid.UUID):
        stopped = threading.Event()

        def heartbeat() -> None:
            while not stopped.wait(JOB_HEARTBEAT_SECONDS):
                try:
                    with session_scope() as session:
                        job = session.get(GenerationJob, job_id)
                        if job is None or not job.status.startswith("generating"):
                            return
                        job.updated_at = utc_now()
                except SQLAlchemyError as exc:
                    print(f"PLP job heartbeat failed: {exc}")

        thread = threading.Thread(
            target=heartbeat,
            name=f"plp-job-heartbeat-{job_id}",
            daemon=True,
        )
        thread.start()
        try:
            yield
        finally:
            stopped.set()
            thread.join(timeout=1)

    def health(self) -> dict:
        try:
            check_database()
            with session_scope() as session:
                skills = session.execute(
                    select(Skill.id, Skill.cefr_level).where(Skill.active.is_(True))
                ).all()
                chunk_metadata = session.scalars(
                    select(CurriculumChunk.metadata_json).where(
                        CurriculumChunk.review_status == "reviewed"
                    )
                ).all()
                source = session.get(CurriculumSource, SOURCE["id"])
                curriculum = assess_curriculum(
                    skills,
                    chunk_metadata,
                    reviewed_source_current=reviewed_source_is_current(
                        source.checksum if source is not None else None
                    ),
                )
            return {
                "database": "ready",
                "curriculum": "ready" if curriculum.ready else "unavailable",
                "worker": (
                    self._worker_thread is not None and self._worker_thread.is_alive()
                ),
            }
        except Exception as exc:
            print(f"PLP health check failed: {exc}")
            return {
                "database": "unavailable",
                "curriculum": "unknown",
                "worker": False,
                "error": "database health check failed",
            }

    def save_profile(self, profile_data: LearnerProfileInput) -> LearnerProfileView:
        try:
            with session_scope() as session:
                _ensure_local_user(session)
                profile = session.scalar(
                    select(LearnerProfile)
                    .where(LearnerProfile.user_id == _user_id())
                    .with_for_update()
                )
                payload = profile_data.model_dump()
                if profile is None:
                    profile = LearnerProfile(user_id=_user_id(), revision=1, **payload)
                    session.add(profile)
                else:
                    profile.revision += 1
                    for key, value in payload.items():
                        setattr(profile, key, value)
                    profile.updated_at = utc_now()
                session.flush()
                return _profile_view(profile)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_profile(self) -> LearnerProfileView:
        try:
            with session_scope() as session:
                profile = session.get(LearnerProfile, _user_id())
                if profile is None:
                    raise PlpNotFoundError("onboarding profile has not been created")
                return _profile_view(profile)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def reset_local_learner(self) -> dict[str, str]:
        """Delete learning state without deleting the authenticated account."""
        try:
            with session_scope() as session:
                user_id = _user_id()
                # "Start over" resets learning, not the account or login.
                for model in (
                    RoleplaySession,
                    RoleplayScenario,
                    SkillEvidence,
                    ActivityAttempt,
                    LessonProgress,
                    StudyDay,
                    LearningPlan,
                    LearnerProfile,
                ):
                    session.execute(delete(model).where(model.user_id == user_id))
            return {"status": "reset"}
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
