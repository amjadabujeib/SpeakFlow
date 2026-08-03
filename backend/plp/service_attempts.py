"""Activity-attempt grading and adaptation proposal behavior."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .database import session_scope
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt, AdaptationProposal, LearningPlan, LessonProgress,
    PlanLesson, SkillEvidence, StudyDay, utc_now,
)
from .schemas import (
    ActivityAttemptInput, ActivityAttemptResult, AdaptationProposalView,
)
from .service_errors import (
    PlpConflictError, PlpInvalidAttemptError, PlpNotFoundError,
    PlpUnavailableError,
)
from .service_grading import (
    _correct_response, _grade_activity, _normalize_text_answer,
    _practice_item_text, _required_activities,
)
from .service_identity import _database_error
from .service_progress import (
    _activity_skill_ids, _latest_lesson_score, _learner_today,
    _passed_pronunciation_targets, _progress_view, _proposal_view,
    _required_pronunciation_targets,
)


class PlpAttemptsMixin:
    def record_attempt(
        self,
        activity_id: str,
        payload: ActivityAttemptInput,
        *,
        trusted_pronunciation: dict | None = None,
    ) -> ActivityAttemptResult:
        try:
            with session_scope() as session:
                lesson = self._find_active_lesson_by_activity(session, activity_id)
                session.execute(
                    select(PlanLesson.id)
                    .where(PlanLesson.id == lesson.id)
                    .with_for_update()
                )
                activity = next(
                    item for item in lesson.content["content"]["activities"]
                    if item["id"] == activity_id
                )
                if lesson.lesson_type == "assessment" and not payload.attempt_session_id:
                    raise PlpInvalidAttemptError(
                        "checkpoint attempts require an attempt_session_id"
                    )
                correct, score, explanation, evidence_allowed = _grade_activity(
                    activity,
                    payload,
                    trusted_pronunciation=trusted_pronunciation,
                )
                if payload.submission_id:
                    existing_attempt = session.scalar(
                        select(ActivityAttempt).where(
                            ActivityAttempt.user_id == _user_id(),
                            ActivityAttempt.submission_id == payload.submission_id,
                        )
                    )
                    if existing_attempt is not None:
                        if (
                            existing_attempt.lesson_id != lesson.id
                            or existing_attempt.activity_id != activity_id
                        ):
                            raise PlpConflictError(
                                "submission_id was already used for another activity"
                            )
                        submitted_response = payload.model_dump(
                            mode="json",
                            exclude_none=True,
                        )
                        stored_response = existing_attempt.response or {}
                        if any(
                            stored_response.get(key) != value
                            for key, value in submitted_response.items()
                        ):
                            raise PlpConflictError(
                                "submission_id was already used for a different response"
                            )
                        progress = session.get(
                            LessonProgress,
                            (_user_id(), lesson.id),
                        )
                        if progress is None:
                            raise PlpUnavailableError(
                                "The recorded attempt is missing its lesson progress."
                            )
                        response_metadata = existing_attempt.response or {}
                        current_lesson_score = _latest_lesson_score(
                            session,
                            lesson,
                            attempt_session_id=(
                                payload.attempt_session_id
                                if lesson.lesson_type == "assessment"
                                else None
                            ),
                        )
                        return ActivityAttemptResult(
                            correct=existing_attempt.correct,
                            score=existing_attempt.score,
                            explanation=explanation,
                            correct_response=_correct_response(activity),
                            first_attempt=bool(
                                response_metadata.get("_first_attempt", False)
                            ),
                            mastery_evidence_recorded=bool(
                                response_metadata.get(
                                    "_mastery_evidence_recorded",
                                    False,
                                )
                            ),
                            lesson_score=current_lesson_score,
                            lesson_completed=progress.status == "completed",
                            newly_completed=False,
                            xp_awarded=0,
                            lesson_progress=_progress_view(
                                progress,
                                len(_required_activities(lesson)),
                            ),
                        )
                previous_attempt_count = session.scalar(
                    select(func.count(ActivityAttempt.id)).where(
                        ActivityAttempt.user_id == _user_id(),
                        ActivityAttempt.lesson_id == lesson.id,
                        ActivityAttempt.activity_id == activity_id,
                    )
                ) or 0
                first_attempt = previous_attempt_count == 0
                response = payload.model_dump(mode="json", exclude_none=True)
                if trusted_pronunciation is not None:
                    response["pronunciation"] = {
                        "target": trusted_pronunciation["target"],
                        "accuracy": trusted_pronunciation["accuracy"],
                        "completeness": trusted_pronunciation["completeness"],
                    }
                attempt = ActivityAttempt(
                    user_id=_user_id(),
                    lesson_id=lesson.id,
                    activity_id=activity_id,
                    submission_id=payload.submission_id,
                    response=response,
                    score=score,
                    correct=correct,
                )
                session.add(attempt)
                session.flush()
                pronunciation_attempts = []
                if activity["type"] == "pronunciation_drill":
                    pronunciation_attempts = session.scalars(
                        select(ActivityAttempt).where(
                            ActivityAttempt.user_id == _user_id(),
                            ActivityAttempt.lesson_id == lesson.id,
                            ActivityAttempt.activity_id == activity_id,
                            ActivityAttempt.correct.is_(True),
                        )
                    ).all()
                progress = session.get(LessonProgress, (_user_id(), lesson.id))
                if progress is None:
                    progress = LessonProgress(
                        user_id=_user_id(),
                        lesson_id=lesson.id,
                        status="in_progress",
                        completed_activity_ids=[],
                        best_score=None,
                        attempts=0,
                    )
                    session.add(progress)
                completed_ids = list(progress.completed_activity_ids or [])
                completes_activity = activity["type"] != "pronunciation_drill"
                if activity["type"] == "pronunciation_drill" and correct is True:
                    passed_targets = _passed_pronunciation_targets(
                        activity,
                        pronunciation_attempts,
                    )
                    required_targets = _required_pronunciation_targets(activity)
                    completes_activity = (
                        bool(required_targets)
                        and required_targets.issubset(passed_targets)
                    )
                    explanation = (
                        f"All {len(required_targets)} assigned pronunciation "
                        "targets passed."
                        if completes_activity
                        else (
                            f"Target passed. {len(passed_targets)} of "
                            f"{len(required_targets)} assigned targets complete."
                        )
                    )
                if completes_activity and activity_id not in completed_ids:
                    completed_ids.append(activity_id)
                progress.completed_activity_ids = completed_ids
                progress.attempts = (progress.attempts or 0) + 1
                mastery_evidence_recorded = (
                    evidence_allowed
                    and first_attempt
                    and payload.attempt_kind == "initial"
                )
                response["_first_attempt"] = first_attempt
                response["_mastery_evidence_recorded"] = (
                    mastery_evidence_recorded
                )
                attempt.response = response
                if mastery_evidence_recorded:
                    weight = 1.5 if lesson.lesson_type == "assessment" else 1.0
                    for skill_id in _activity_skill_ids(activity, lesson):
                        session.add(
                            SkillEvidence(
                                user_id=_user_id(),
                                skill_id=skill_id,
                                attempt_id=attempt.id,
                                score=score,
                                weight=weight,
                            )
                        )
                current_lesson_score = _latest_lesson_score(
                    session,
                    lesson,
                    attempt_session_id=(
                        payload.attempt_session_id
                        if lesson.lesson_type == "assessment"
                        else None
                    ),
                )
                if current_lesson_score is not None:
                    progress.best_score = max(
                        progress.best_score or 0,
                        current_lesson_score,
                    )
                session.merge(
                    StudyDay(
                        user_id=_user_id(),
                        studied_on=_learner_today(
                            payload.timezone_offset_minutes
                        ),
                    )
                )
                was_completed = progress.status == "completed"
                lesson_completed = self._update_lesson_completion(
                    session,
                    lesson,
                    progress,
                    attempt_session_id=payload.attempt_session_id,
                )
                newly_completed = lesson_completed and not was_completed
                if newly_completed:
                    self._queue_next_generation(session, lesson.revision_id)
                session.flush()
                return ActivityAttemptResult(
                    correct=correct,
                    score=score,
                    explanation=explanation,
                    correct_response=_correct_response(activity),
                    first_attempt=first_attempt,
                    mastery_evidence_recorded=mastery_evidence_recorded,
                    lesson_score=current_lesson_score,
                    lesson_completed=lesson_completed,
                    newly_completed=newly_completed,
                    xp_awarded=lesson.xp if newly_completed else 0,
                    lesson_progress=_progress_view(progress, len(_required_activities(lesson))),
                )
        except StopIteration as exc:
            raise PlpNotFoundError("activity was not found in the active plan") from exc
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def validate_pronunciation_target(
        self,
        activity_id: str,
        target: str,
    ) -> str:
        try:
            with session_scope() as session:
                lesson = self._find_active_lesson_by_activity(session, activity_id)
                activity = next(
                    item for item in lesson.content["content"]["activities"]
                    if item["id"] == activity_id
                )
                if activity["type"] != "pronunciation_drill":
                    raise PlpInvalidAttemptError(
                        "the selected lesson activity is not a pronunciation check"
                    )
                normalized = _normalize_text_answer(target)
                allowed = {
                    _normalize_text_answer(_practice_item_text(item)): item
                    for item in activity["data"].get("practice_items", [])
                }
                if normalized not in allowed:
                    raise PlpInvalidAttemptError(
                        "choose one of this lesson's assigned pronunciation targets"
                    )
                return _practice_item_text(allowed[normalized])
        except StopIteration as exc:
            raise PlpNotFoundError("activity was not found in the active plan") from exc
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def list_adaptation_proposals(self) -> list[AdaptationProposalView]:
        try:
            with session_scope() as session:
                plan = self._active_plan(session)
                if plan is None:
                    return []
                proposals = session.scalars(
                    select(AdaptationProposal)
                    .where(AdaptationProposal.plan_id == plan.id)
                    .order_by(AdaptationProposal.created_at.desc())
                ).all()
                return [_proposal_view(item) for item in proposals]
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def create_adaptation_proposal(self) -> AdaptationProposalView:
        try:
            with session_scope() as session:
                plan = self._active_plan(session)
                if plan is None or plan.active_revision_id is None:
                    raise PlpConflictError("a ready plan is required")
                rows = session.execute(
                    select(
                        SkillEvidence.skill_id,
                        func.count(SkillEvidence.id),
                        func.count(func.distinct(ActivityAttempt.lesson_id)),
                        func.sum(SkillEvidence.score * SkillEvidence.weight) /
                        func.sum(SkillEvidence.weight),
                    )
                    .join(
                        ActivityAttempt,
                        ActivityAttempt.id == SkillEvidence.attempt_id,
                    )
                    .where(SkillEvidence.user_id == _user_id())
                    .group_by(SkillEvidence.skill_id)
                ).all()
                weak = [
                    {
                        "skill_id": row[0],
                        "evidence_count": int(row[1]),
                        "lesson_count": int(row[2]),
                        "weighted_score": round(float(row[3]), 1),
                    }
                    for row in rows
                    if int(row[1]) >= 2 and int(row[2]) >= 2 and float(row[3]) < 70
                ]
                if not weak:
                    raise PlpConflictError(
                        "there is not enough repeated weak-skill evidence for a proposal"
                    )
                changes = [
                    {
                        "action": "reinforce",
                        "skill_id": item["skill_id"],
                        "scope": "unstarted_future_lessons",
                    }
                    for item in weak
                ]
                proposal = AdaptationProposal(
                    plan_id=plan.id,
                    base_revision_id=plan.active_revision_id,
                    status="pending",
                    summary="Reinforce skills with repeated scores below 70% in future unstarted lessons.",
                    changes=changes,
                    evidence=weak,
                )
                session.add(proposal)
                session.flush()
                return _proposal_view(proposal)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def decide_adaptation(self, proposal_id: uuid.UUID, approve: bool) -> dict:
        try:
            if approve:
                generation = self.create_generation(
                    reason=f"adaptation:{proposal_id}"
                )
                return {
                    "status": "approved",
                    "proposal_id": str(proposal_id),
                    "generation": generation.model_dump(mode="json"),
                }
            with session_scope() as session:
                proposal = session.scalar(
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
                if proposal is None:
                    raise PlpNotFoundError("adaptation proposal was not found")
                if proposal.status != "pending":
                    raise PlpConflictError("adaptation proposal has already been decided")
                proposal.status = "rejected"
                proposal.decided_at = utc_now()
            return {"status": "rejected", "proposal_id": str(proposal_id)}
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
