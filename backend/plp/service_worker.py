"""Generation-job claiming, leasing, retry, and failure behavior."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import session_scope
from .generator import GenerationError
from .models import GenerationJob, LearningPlan, PlanLesson, PlanRevision, utc_now
from .retrieval import RetrievalError
from .service_errors import (
    DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS, JOB_LEASE_SECONDS,
)
from .service_grading import (
    _classify_failure, _decode_job_failure, _encode_job_failure,
)
from .service_identity import _unexpected_worker_error
from .service_progress import _eligible_pending_lesson_ids, _retry_available_at
from .standard import PLP_ARCHITECTURE


class PlpWorkerMixin:
    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            job_id = None
            try:
                job_id = self._claim_next_job()
                if job_id is None:
                    self._stop_event.wait(2.0)
                    continue
                self._process_job(job_id)
            except Exception as exc:
                print(f"PLP worker error: {exc}")
                if job_id is not None:
                    self._mark_job_failed(
                        job_id,
                        None,
                        _unexpected_worker_error(exc),
                    )
                self._stop_event.wait(3.0)

    def _claim_next_job(self) -> uuid.UUID | None:
        try:
            with session_scope() as session:
                stale_cutoff = utc_now() - timedelta(seconds=JOB_LEASE_SECONDS)
                stale_jobs = session.scalars(
                    select(GenerationJob)
                    .where(
                        GenerationJob.status.in_(
                            (
                                "generating_week_one",
                                "generating_future_weeks",
                                "generating_initial",
                                "generating_next",
                            )
                        ),
                        GenerationJob.updated_at < stale_cutoff,
                    )
                    .with_for_update(skip_locked=True)
                ).all()
                for stale_job in stale_jobs:
                    stale_job.status = "queued"
                    stale_job.error = None
                waiting_jobs = session.scalars(
                    select(GenerationJob)
                    .where(GenerationJob.status == "waiting_for_model")
                    .order_by(GenerationJob.updated_at)
                    .with_for_update(skip_locked=True)
                ).all()
                now = utc_now()
                for waiting_job in waiting_jobs:
                    failure = _decode_job_failure(waiting_job.error)
                    retry_at = _retry_available_at(waiting_job, failure)
                    if retry_at is None or retry_at <= now:
                        waiting_job.status = "queued"
                        waiting_job.error = None
                job = session.scalar(
                    select(GenerationJob)
                    .where(GenerationJob.status == "queued")
                    .order_by(GenerationJob.created_at)
                    .with_for_update(skip_locked=True)
                )
                if job is None:
                    return None
                ready_count = session.scalar(
                    select(func.count(PlanLesson.id)).where(
                        PlanLesson.revision_id == job.revision_id,
                        PlanLesson.content_status == "ready",
                    )
                )
                job.status = (
                    "generating_initial" if not ready_count else "generating_next"
                )
                job.attempts += 1
                job.error = None
                job.updated_at = utc_now()
                return job.id
        except SQLAlchemyError as exc:
            print(f"PLP worker could not claim a generation job: {exc}")
            return None

    def _process_job(self, job_id: uuid.UUID) -> None:
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            eligible_ids = _eligible_pending_lesson_ids(session, job.revision_id)
            first_eligible = (
                session.get(PlanLesson, eligible_ids[0]) if eligible_ids else None
            )
            is_weekly_mission = bool(
                first_eligible
                and first_eligible.specification.get("architecture")
                == PLP_ARCHITECTURE
            )
            mission_week = first_eligible.week_sequence if first_eligible else None
            if is_weekly_mission:
                job.status = (
                    "generating_week_one"
                    if mission_week == 1
                    else "generating_future_weeks"
                )
                job.updated_at = utc_now()
        if not eligible_ids:
            with session_scope() as session:
                job = session.get(GenerationJob, job_id)
                if job is not None:
                    pending_count = session.scalar(
                        select(func.count(PlanLesson.id)).where(
                            PlanLesson.revision_id == job.revision_id,
                            PlanLesson.content_status == "pending",
                        )
                    )
                    job.status = "idle" if pending_count else "complete"
            return
        if is_weekly_mission:
            try:
                with self._job_lease(job_id):
                    self._generate_week(job_id, int(mission_week))
            except GenerationError as exc:
                if exc.failure_kind == "rate_limited":
                    self._defer_job_for_rate_limit(
                        job_id,
                        eligible_ids[0],
                        exc,
                    )
                    return
                self._mark_job_failed(job_id, eligible_ids[0], exc)
                return
            except RetrievalError as exc:
                self._mark_job_failed(job_id, eligible_ids[0], exc)
                return
            except Exception as exc:
                self._mark_job_failed(
                    job_id,
                    eligible_ids[0],
                    _unexpected_worker_error(exc),
                )
                return
        else:
            # Non-weekly lesson shells use the focused per-lesson generator.
            batch_limit = 4 if self.generator.provider == "curated" else 1
            for lesson_id in eligible_ids[:batch_limit]:
                if self._stop_event.is_set():
                    return
                try:
                    with self._job_lease(job_id):
                        self._generate_lesson(job_id, lesson_id)
                except (RetrievalError, GenerationError) as exc:
                    self._mark_job_failed(job_id, lesson_id, exc)
                    return
                except Exception as exc:
                    self._mark_job_failed(
                        job_id,
                        lesson_id,
                        _unexpected_worker_error(exc),
                    )
                    return
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            revision = session.get(PlanRevision, job.revision_id)
            assert revision is not None
            plan = session.get(LearningPlan, revision.plan_id)
            assert plan is not None
            pending_count = session.scalar(
                select(func.count(PlanLesson.id)).where(
                    PlanLesson.revision_id == revision.id,
                    PlanLesson.content_status == "pending",
                )
            )
            job.status = "idle" if pending_count else "complete"
            revision.status = "active_jit" if pending_count else "ready"
            plan.active_revision_id = revision.id

    @staticmethod
    def _defer_job_for_rate_limit(
        job_id: uuid.UUID,
        lesson_id: uuid.UUID | None,
        failure: GenerationError,
    ) -> None:
        """Keep a rejected week pending and resume after Groq's token window."""
        retry_after_seconds = failure.retry_after_seconds
        if retry_after_seconds is None:
            retry_after_seconds = DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        retry_after_seconds = max(1, min(300, int(retry_after_seconds)))
        message = (
            "Groq's token window is briefly full. Your roadmap is safe and "
            f"generation will continue automatically in about "
            f"{retry_after_seconds} seconds."
        )
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            lesson = session.get(PlanLesson, lesson_id) if lesson_id else None
            if lesson is None:
                lesson = session.scalar(
                    select(PlanLesson)
                    .where(
                        PlanLesson.revision_id == job.revision_id,
                        PlanLesson.content_status == "pending",
                    )
                    .order_by(PlanLesson.week_sequence, PlanLesson.lesson_sequence)
                )
            cohort = [lesson] if lesson is not None else []
            if (
                lesson is not None
                and lesson.specification.get("architecture") == PLP_ARCHITECTURE
            ):
                cohort = session.scalars(
                    select(PlanLesson).where(
                        PlanLesson.revision_id == lesson.revision_id,
                        PlanLesson.week_sequence == lesson.week_sequence,
                        PlanLesson.content_status.in_(("pending", "failed")),
                    )
                ).all()
            for cohort_lesson in cohort:
                cohort_lesson.content_status = "pending"
                cohort_lesson.generation_error = None
                # A 429 produces no candidate, so retry the same deterministic
                # writer variant instead of consuming a content attempt.
                cohort_lesson.generation_attempts = max(
                    0,
                    cohort_lesson.generation_attempts - 1,
                )
            job.status = "waiting_for_model"
            job.error = _encode_job_failure(
                message,
                failure_kind="rate_limited",
                retry_after_seconds=retry_after_seconds,
            )
            job.updated_at = utc_now()

    @staticmethod
    def _mark_job_failed(
        job_id: uuid.UUID,
        lesson_id: uuid.UUID | None,
        failure: str | Exception,
    ) -> None:
        message = str(failure)
        failure_kind = getattr(failure, "failure_kind", None)
        retry_after_seconds = getattr(failure, "retry_after_seconds", None)
        if not failure_kind:
            failure_kind = _classify_failure(message)
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            lesson = session.get(PlanLesson, lesson_id) if lesson_id else None
            if lesson is None:
                lesson = session.scalar(
                    select(PlanLesson)
                    .where(
                        PlanLesson.revision_id == job.revision_id,
                        PlanLesson.content_status == "pending",
                    )
                    .order_by(PlanLesson.week_sequence, PlanLesson.lesson_sequence)
                )
            if lesson is not None:
                cohort = [lesson]
                if lesson.specification.get("architecture") == PLP_ARCHITECTURE:
                    cohort = session.scalars(
                        select(PlanLesson).where(
                            PlanLesson.revision_id == lesson.revision_id,
                            PlanLesson.week_sequence == lesson.week_sequence,
                            PlanLesson.content_status.in_(("pending", "failed")),
                        )
                    ).all()
                for cohort_lesson in cohort:
                    cohort_lesson.generation_error = message
                    cohort_lesson.content_status = "failed"
            job.status = "failed"
            job.error = _encode_job_failure(
                message,
                failure_kind=failure_kind,
                retry_after_seconds=retry_after_seconds,
            )
            job.updated_at = utc_now()

    @staticmethod
    def _queue_next_generation(session: Session, revision_id: uuid.UUID) -> None:
        """Queue content only when its learning prerequisites are complete."""
        job = session.scalar(
            select(GenerationJob).where(GenerationJob.revision_id == revision_id)
        )
        if job is None or job.status != "idle":
            return
        if _eligible_pending_lesson_ids(session, revision_id):
            job.status = "queued"
            job.error = None
