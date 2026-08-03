"""Learning-plan generation request and retrieval behavior."""

from __future__ import annotations

import copy
import math
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .database import session_scope
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt, AdaptationProposal, GenerationJob, LearnerProfile,
    LearningPlan, LessonProgress, PlanLesson, PlanRevision, Skill,
    SkillEvidence, SkillPrerequisite, utc_now,
)
from .planner import PlanningSkill, build_outline
from .schemas import GenerationAccepted, GenerationView, PlpDocument
from .service_errors import PlpConflictError, PlpNotFoundError
from .service_grading import _decode_job_failure
from .service_identity import _database_error, _learner_snapshot, _profile_input
from .service_progress import _retry_available_at


class PlpGenerationMixin:
    def create_generation(self, *, reason: str = "onboarding") -> GenerationAccepted:
        try:
            with session_scope() as session:
                profile = session.scalar(
                    select(LearnerProfile)
                    .where(LearnerProfile.user_id == _user_id())
                    .with_for_update()
                )
                if profile is None:
                    raise PlpConflictError("complete onboarding before generating a plan")
                existing = session.scalar(
                    select(GenerationJob)
                    .join(PlanRevision, GenerationJob.revision_id == PlanRevision.id)
                    .join(LearningPlan, PlanRevision.plan_id == LearningPlan.id)
                    .where(
                        LearningPlan.user_id == _user_id(),
                        GenerationJob.status.in_((
                            "queued", "generating_week_one", "generating_future_weeks",
                            "waiting_for_model", "generating_initial", "generating_next",
                        )),
                    )
                    .order_by(GenerationJob.created_at.desc())
                )
                if existing is not None:
                    if reason.startswith("adaptation:"):
                        raise PlpConflictError(
                            "finish the current plan generation before applying an adaptation"
                        )
                    revision = session.get(PlanRevision, existing.revision_id)
                    assert revision is not None
                    return GenerationAccepted(
                        job_id=existing.id, plan_id=revision.plan_id, status="queued"
                    )

                skill_rows = session.scalars(
                    select(Skill).where(Skill.active.is_(True))
                ).all()
                planning_skills = [
                    PlanningSkill(
                        id=skill.id,
                        domain=skill.domain,
                        level=skill.cefr_level,
                        title=skill.title,
                        description=skill.description,
                        outcomes=list(skill.outcomes),
                    )
                    for skill in skill_rows
                ]
                prerequisites_by_skill: dict[str, list[str]] = defaultdict(list)
                for skill_id, prerequisite_id in session.execute(
                    select(
                        SkillPrerequisite.skill_id,
                        SkillPrerequisite.prerequisite_skill_id,
                    )
                ).all():
                    prerequisites_by_skill[skill_id].append(prerequisite_id)
                mastered_skill_ids = {
                    row[0]
                    for row in session.execute(
                        select(
                            SkillEvidence.skill_id,
                            func.count(func.distinct(ActivityAttempt.lesson_id)),
                            func.sum(SkillEvidence.score * SkillEvidence.weight)
                            / func.sum(SkillEvidence.weight),
                        )
                        .join(
                            ActivityAttempt,
                            ActivityAttempt.id == SkillEvidence.attempt_id,
                        )
                        .where(SkillEvidence.user_id == _user_id())
                        .group_by(SkillEvidence.skill_id)
                    ).all()
                    if int(row[1] or 0) >= 2
                    and row[2] is not None
                    and float(row[2]) >= 75
                }
                profile_input = _profile_input(profile)
                base_revision = None
                adaptation_proposal = None
                priority_skill_ids: list[str] = []
                if reason.startswith("adaptation:"):
                    proposal_id = uuid.UUID(reason.split(":", 1)[1])
                    adaptation_proposal = session.scalar(
                        select(AdaptationProposal)
                        .join(
                            LearningPlan,
                            AdaptationProposal.plan_id == LearningPlan.id,
                        )
                        .where(
                            AdaptationProposal.id == proposal_id,
                            LearningPlan.user_id == _user_id(),
                        )
                        .with_for_update()
                    )
                    if adaptation_proposal is None:
                        raise PlpNotFoundError("adaptation proposal was not found")
                    if adaptation_proposal.status != "pending":
                        raise PlpConflictError(
                            "adaptation proposal has already been decided"
                        )
                    base_revision = session.get(
                        PlanRevision,
                        adaptation_proposal.base_revision_id,
                    )
                    priority_skill_ids = [
                        change["skill_id"]
                        for change in adaptation_proposal.changes
                        if change.get("action") == "reinforce" and change.get("skill_id")
                    ]
                outline = build_outline(
                    profile_input,
                    planning_skills,
                    priority_skill_ids=priority_skill_ids,
                    prerequisites_by_skill=dict(prerequisites_by_skill),
                    mastered_skill_ids=mastered_skill_ids,
                    variation_seed=uuid.uuid4().hex,
                )
                locked_weeks = 0
                old_lessons_by_key: dict[str, PlanLesson] = {}
                old_progress_by_key: dict[str, LessonProgress] = {}
                old_attempts_by_key: dict[str, list[ActivityAttempt]] = defaultdict(list)
                if base_revision is not None:
                    old_lessons = session.scalars(
                        select(PlanLesson)
                        .where(PlanLesson.revision_id == base_revision.id)
                        .order_by(PlanLesson.week_sequence, PlanLesson.lesson_sequence)
                    ).all()
                    old_by_id = {lesson.id: lesson for lesson in old_lessons}
                    progress_rows = session.scalars(
                        select(LessonProgress).where(
                            LessonProgress.user_id == _user_id(),
                            LessonProgress.lesson_id.in_(old_by_id),
                        )
                    ).all() if old_by_id else []
                    if progress_rows:
                        locked_weeks = max(
                            old_by_id[row.lesson_id].week_sequence for row in progress_rows
                        )
                    if locked_weeks:
                        old_weeks = {
                            week["sequence"]: copy.deepcopy(week)
                            for week in base_revision.outline["weeks"]
                            if week["sequence"] <= locked_weeks
                        }
                        outline["weeks"] = [
                            old_weeks.get(week["sequence"], week)
                            for week in outline["weeks"]
                        ]
                        old_lessons_by_key = {
                            lesson.lesson_key: lesson
                            for lesson in old_lessons
                            if lesson.week_sequence <= locked_weeks
                        }
                        old_progress_by_key = {
                            old_by_id[row.lesson_id].lesson_key: row
                            for row in progress_rows
                            if old_by_id[row.lesson_id].week_sequence <= locked_weeks
                        }
                        for attempt in session.scalars(
                            select(ActivityAttempt).where(
                                ActivityAttempt.user_id == _user_id(),
                                ActivityAttempt.lesson_id.in_(
                                    [item.id for item in old_lessons_by_key.values()]
                                ),
                            )
                        ).all():
                            old_attempts_by_key[old_by_id[attempt.lesson_id].lesson_key].append(
                                attempt
                            )
                plan = session.scalar(
                    select(LearningPlan)
                    .where(LearningPlan.user_id == _user_id())
                    .order_by(LearningPlan.created_at.desc())
                )
                if plan is None:
                    plan = LearningPlan(user_id=_user_id())
                    session.add(plan)
                    session.flush()
                max_revision = session.scalar(
                    select(func.max(PlanRevision.revision)).where(
                        PlanRevision.plan_id == plan.id
                    )
                ) or 0
                revision = PlanRevision(
                    plan_id=plan.id,
                    revision=max_revision + 1,
                    status="generating",
                    learner_snapshot=_learner_snapshot(profile),
                    outline=outline,
                    generation_reason=reason,
                )
                session.add(revision)
                session.flush()
                new_lessons_by_key: dict[str, PlanLesson] = {}
                for week in outline["weeks"]:
                    for unit in week["units"]:
                        for lesson in unit["lessons"]:
                            old_lesson = old_lessons_by_key.get(lesson["lesson_key"])
                            new_lesson = PlanLesson(
                                revision_id=revision.id,
                                lesson_key=lesson["lesson_key"],
                                week_sequence=week["sequence"],
                                unit_sequence=unit["sequence"],
                                lesson_sequence=lesson["sequence"],
                                lesson_type=lesson["type"],
                                estimated_minutes=lesson["estimated_minutes"],
                                xp=lesson["xp"],
                                skill_ids=lesson["skill_ids"],
                                required_lesson_keys=lesson["required_lesson_keys"],
                                specification=lesson["specification"],
                                content_status=(
                                    old_lesson.content_status if old_lesson else "pending"
                                ),
                                content=(
                                    copy.deepcopy(old_lesson.content)
                                    if old_lesson else None
                                ),
                                source_refs=(
                                    list(old_lesson.source_refs) if old_lesson else []
                                ),
                                generation_attempts=(
                                    old_lesson.generation_attempts if old_lesson else 0
                                ),
                                generation_error=(
                                    old_lesson.generation_error if old_lesson else None
                                ),
                            )
                            session.add(new_lesson)
                            new_lessons_by_key[lesson["lesson_key"]] = new_lesson
                session.flush()
                for lesson_key, old_progress in old_progress_by_key.items():
                    new_lesson = new_lessons_by_key[lesson_key]
                    session.add(
                        LessonProgress(
                            user_id=_user_id(),
                            lesson_id=new_lesson.id,
                            status=old_progress.status,
                            completed_activity_ids=list(old_progress.completed_activity_ids),
                            best_score=old_progress.best_score,
                            attempts=old_progress.attempts,
                            started_at=old_progress.started_at,
                            completed_at=old_progress.completed_at,
                        )
                    )
                    for old_attempt in old_attempts_by_key[lesson_key]:
                        session.add(
                            ActivityAttempt(
                                user_id=_user_id(),
                                lesson_id=new_lesson.id,
                                activity_id=old_attempt.activity_id,
                                response=copy.deepcopy(old_attempt.response),
                                score=old_attempt.score,
                                correct=old_attempt.correct,
                                created_at=old_attempt.created_at,
                            )
                        )
                job = GenerationJob(revision_id=revision.id, status="queued")
                session.add(job)
                # The deterministic outline is useful immediately. Generated
                # lesson bodies arrive just-in-time and never block plan display.
                revision.status = "ready_outline"
                if plan.active_revision_id is None:
                    plan.active_revision_id = revision.id
                if adaptation_proposal is not None:
                    adaptation_proposal.status = "approved"
                    adaptation_proposal.decided_at = utc_now()
                session.flush()
                return GenerationAccepted(job_id=job.id, plan_id=plan.id)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_generation(self, job_id: uuid.UUID) -> GenerationView:
        try:
            with session_scope() as session:
                job = session.scalar(
                    select(GenerationJob)
                    .join(
                        PlanRevision,
                        GenerationJob.revision_id == PlanRevision.id,
                    )
                    .join(LearningPlan, PlanRevision.plan_id == LearningPlan.id)
                    .where(
                        GenerationJob.id == job_id,
                        LearningPlan.user_id == _user_id(),
                    )
                )
                if job is None:
                    raise PlpNotFoundError("generation job was not found")
                return self._generation_view(session, job)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_latest_generation(self) -> GenerationView:
        try:
            with session_scope() as session:
                job = session.scalar(
                    select(GenerationJob)
                    .join(PlanRevision, GenerationJob.revision_id == PlanRevision.id)
                    .join(LearningPlan, PlanRevision.plan_id == LearningPlan.id)
                    .where(LearningPlan.user_id == _user_id())
                    .order_by(GenerationJob.created_at.desc())
                )
                if job is None:
                    raise PlpNotFoundError("no plan generation has been created")
                return self._generation_view(session, job)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def retry_generation(self, job_id: uuid.UUID) -> GenerationView:
        try:
            with session_scope() as session:
                job = session.scalar(
                    select(GenerationJob)
                    .join(
                        PlanRevision,
                        GenerationJob.revision_id == PlanRevision.id,
                    )
                    .join(LearningPlan, PlanRevision.plan_id == LearningPlan.id)
                    .where(
                        GenerationJob.id == job_id,
                        LearningPlan.user_id == _user_id(),
                    )
                )
                if job is None:
                    raise PlpNotFoundError("generation job was not found")
                if job.status != "failed":
                    raise PlpConflictError("only a failed generation job can be retried")
                failure = _decode_job_failure(job.error)
                retry_available_at = _retry_available_at(job, failure)
                if retry_available_at is not None and utc_now() < retry_available_at:
                    remaining = math.ceil(
                        (retry_available_at - utc_now()).total_seconds()
                    )
                    raise PlpConflictError(
                        "Groq is still rate-limited. "
                        f"Retry in {max(1, remaining)} seconds."
                    )
                failed = session.scalars(
                    select(PlanLesson).where(
                        PlanLesson.revision_id == job.revision_id,
                        PlanLesson.content_status == "failed",
                    )
                ).all()
                if not failed:
                    raise PlpConflictError("generation has no failed lessons to retry")
                for lesson in failed:
                    lesson.content_status = "pending"
                    lesson.generation_error = None
                job.status = "queued"
                job.error = None
                session.flush()
                return self._generation_view(session, job)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def get_active_document(self) -> PlpDocument:
        try:
            with session_scope() as session:
                plan = session.scalar(
                    select(LearningPlan)
                    .where(
                        LearningPlan.user_id == _user_id(),
                        LearningPlan.active_revision_id.is_not(None),
                    )
                    .order_by(LearningPlan.created_at.desc())
                )
                if plan is None or plan.active_revision_id is None:
                    raise PlpNotFoundError("no generated plan is ready yet")
                revision = session.get(PlanRevision, plan.active_revision_id)
                if revision is None:
                    raise PlpNotFoundError("active plan revision is missing")
                job = session.scalar(
                    select(GenerationJob).where(GenerationJob.revision_id == revision.id)
                )
                if job is None:
                    raise PlpNotFoundError("active plan generation record is missing")
                return self._build_document(session, plan, revision, job)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
