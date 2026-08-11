"""Activity-attempt grading and progress behavior."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from speakflow.features.pronunciation.domain import (
    PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT,
)

from .database import session_scope
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt,
    LessonProgress,
    PlanLesson,
    SkillEvidence,
    StudyDay,
)
from .pronunciation_attempt_policy import (
    pronunciation_attempt_response,
    pronunciation_evidence_weight,
    pronunciation_progress_explanation,
    should_accept_inconclusive_progress,
    should_record_pronunciation_evidence,
)
from .schemas import ActivityAttemptInput, ActivityAttemptResult
from .service_errors import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
)
from .service_grading import (
    _correct_response,
    _grade_activity,
    _required_activities,
)
from .service_identity import _database_error
from .service_progress import (
    _activity_skill_ids,
    _completed_pronunciation_targets,
    _latest_lesson_score,
    _learner_today,
    _progress_view,
    _pronunciation_activity_complete,
    _pronunciation_activity_progress,
    _required_pronunciation_targets,
    _verified_completed_activity_ids,
    _visible_lesson_status,
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
                    item
                    for item in lesson.content["content"]["activities"]
                    if item["id"] == activity_id
                )
                if (
                    lesson.lesson_type == "assessment"
                    and not payload.attempt_session_id
                ):
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
                        stored_pronunciation = response_metadata.get("pronunciation")
                        pronunciation_target_completed = bool(
                            isinstance(stored_pronunciation, dict)
                            and (
                                existing_attempt.correct is True
                                or stored_pronunciation.get("completion_accepted")
                                is True
                            )
                        )
                        if (
                            isinstance(stored_pronunciation, dict)
                            and stored_pronunciation.get("completion_accepted") is True
                        ):
                            explanation = (
                                "This target remained inconclusive after "
                                f"{PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT} attempts, "
                                "so you may continue without a pronunciation "
                                "mastery record."
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
                        return ActivityAttemptResult(
                            correct=existing_attempt.correct,
                            score=existing_attempt.score,
                            diagnostic_score=(
                                stored_pronunciation.get("diagnostic_score")
                                if isinstance(stored_pronunciation, dict)
                                else None
                            ),
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
                            pronunciation_target_completed=(
                                pronunciation_target_completed
                            ),
                            pronunciation_mastery_verified=(
                                existing_attempt.correct
                                if isinstance(stored_pronunciation, dict)
                                else None
                            ),
                            lesson_score=current_lesson_score,
                            lesson_completed=progress.status == "completed",
                            newly_completed=False,
                            xp_awarded=0,
                            lesson_progress=_progress_view(
                                progress,
                                len(_required_activities(lesson)),
                                pronunciation_activity_progress=(
                                    _pronunciation_activity_progress(session, lesson)
                                ),
                            ),
                        )
                previous_attempt_count = (
                    session.scalar(
                        select(func.count(ActivityAttempt.id)).where(
                            ActivityAttempt.user_id == _user_id(),
                            ActivityAttempt.lesson_id == lesson.id,
                            ActivityAttempt.activity_id == activity_id,
                        )
                    )
                    or 0
                )
                first_attempt = previous_attempt_count == 0
                prior_pronunciation_attempts = []
                all_prior_pronunciation_attempts = []
                pronunciation_progress_accepted = False
                if activity["type"] == "pronunciation_drill":
                    pronunciation_query = select(ActivityAttempt).where(
                        ActivityAttempt.user_id == _user_id(),
                        ActivityAttempt.lesson_id == lesson.id,
                        ActivityAttempt.activity_id == activity_id,
                    )
                    all_prior_pronunciation_attempts = session.scalars(
                        pronunciation_query
                    ).all()
                    prior_pronunciation_attempts = all_prior_pronunciation_attempts
                    if lesson.lesson_type == "assessment":
                        prior_pronunciation_attempts = [
                            attempt
                            for attempt in all_prior_pronunciation_attempts
                            if (attempt.response or {}).get("attempt_session_id")
                            == payload.attempt_session_id
                        ]
                    if correct is None and trusted_pronunciation is not None:
                        pronunciation_progress_accepted = (
                            should_accept_inconclusive_progress(
                                prior_pronunciation_attempts,
                                str(trusted_pronunciation.get("target", "")),
                            )
                        )
                response = payload.model_dump(mode="json", exclude_none=True)
                if trusted_pronunciation is not None:
                    response["pronunciation"] = pronunciation_attempt_response(
                        trusted_pronunciation,
                        completion_accepted=pronunciation_progress_accepted,
                    )
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
                    pronunciation_attempts = [
                        *prior_pronunciation_attempts,
                        attempt,
                    ]
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
                completion_previously_recorded = bool(
                    progress.status == "completed" or progress.completed_at is not None
                )
                completed_ids = list(progress.completed_activity_ids or [])
                legacy_pronunciation_was_unverified = (
                    activity["type"] == "pronunciation_drill"
                    and activity_id in completed_ids
                    and not _pronunciation_activity_complete(
                        activity,
                        all_prior_pronunciation_attempts,
                    )
                )
                completes_activity = activity["type"] != "pronunciation_drill"
                pronunciation_target_completed = activity[
                    "type"
                ] == "pronunciation_drill" and (
                    correct is True or pronunciation_progress_accepted
                )
                if pronunciation_target_completed:
                    completed_targets = _completed_pronunciation_targets(
                        activity,
                        pronunciation_attempts,
                    )
                    required_targets = _required_pronunciation_targets(activity)
                    completes_activity = bool(
                        required_targets
                    ) and required_targets.issubset(completed_targets)
                    explanation = pronunciation_progress_explanation(
                        activity_completed=completes_activity,
                        progress_accepted=pronunciation_progress_accepted,
                        completed_targets=len(completed_targets),
                        required_targets=len(required_targets),
                    )
                if completes_activity and activity_id not in completed_ids:
                    completed_ids.append(activity_id)
                progress.completed_activity_ids = completed_ids
                visible_completed_ids = _verified_completed_activity_ids(
                    session,
                    lesson,
                    progress,
                )
                progress.completed_activity_ids = visible_completed_ids
                progress.status = _visible_lesson_status(
                    progress,
                    _required_activities(lesson),
                    visible_completed_ids,
                )
                status_before_completion = progress.status
                progress.attempts = (progress.attempts or 0) + 1
                mastery_evidence_recorded = (
                    should_record_pronunciation_evidence(
                        all_prior_pronunciation_attempts,
                        target=str((trusted_pronunciation or {}).get("target", "")),
                        evidence_allowed=evidence_allowed,
                        attempt_kind=payload.attempt_kind,
                    )
                    if activity["type"] == "pronunciation_drill"
                    else evidence_allowed
                    and first_attempt
                    and payload.attempt_kind == "initial"
                )
                response["_first_attempt"] = first_attempt
                response["_mastery_evidence_recorded"] = mastery_evidence_recorded
                attempt.response = response
                if mastery_evidence_recorded:
                    weight = 1.5 if lesson.lesson_type == "assessment" else 1.0
                    if activity["type"] == "pronunciation_drill":
                        # A sound drill produces one attempt per assigned target.
                        # Split the normal activity weight across those targets so
                        # a longer word list cannot dominate adaptive evidence.
                        weight = pronunciation_evidence_weight(
                            base_weight=weight,
                            assigned_target_count=len(
                                _required_pronunciation_targets(activity)
                            ),
                        )
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
                        studied_on=_learner_today(payload.timezone_offset_minutes),
                    )
                )
                lesson_completed = self._update_lesson_completion(
                    session,
                    lesson,
                    progress,
                    attempt_session_id=payload.attempt_session_id,
                )
                newly_completed = (
                    lesson_completed and not completion_previously_recorded
                )
                if lesson_completed and (
                    status_before_completion != "completed"
                    or legacy_pronunciation_was_unverified
                ):
                    self._queue_next_generation(session, lesson.revision_id)
                session.flush()
                return ActivityAttemptResult(
                    correct=correct,
                    score=score,
                    diagnostic_score=(
                        trusted_pronunciation.get("diagnostic_score")
                        if trusted_pronunciation is not None
                        else None
                    ),
                    explanation=explanation,
                    correct_response=_correct_response(activity),
                    first_attempt=first_attempt,
                    mastery_evidence_recorded=mastery_evidence_recorded,
                    pronunciation_target_completed=(pronunciation_target_completed),
                    pronunciation_mastery_verified=(
                        correct if activity["type"] == "pronunciation_drill" else None
                    ),
                    lesson_score=current_lesson_score,
                    lesson_completed=lesson_completed,
                    newly_completed=newly_completed,
                    xp_awarded=lesson.xp if newly_completed else 0,
                    lesson_progress=_progress_view(
                        progress,
                        len(_required_activities(lesson)),
                        pronunciation_activity_progress=(
                            _pronunciation_activity_progress(session, lesson)
                        ),
                    ),
                )
        except StopIteration as exc:
            raise PlpNotFoundError("activity was not found in the active plan") from exc
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
