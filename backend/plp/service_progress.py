"""Progress, streak, retry, proposal, and roleplay view helpers."""

from __future__ import annotations

import copy
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt, AdaptationProposal, GenerationJob, LearningPlan,
    LessonProgress, PlanLesson, PlanRevision, RoleplaySession, RoleplayTurn,
    utc_now,
)
from .schemas import (
    AdaptationProposalView, LessonProgressView, RoleplaySessionView,
)
from .service_errors import DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
from .service_grading import (
    _normalize_text_answer, _practice_item_text, _scored_activities,
)


def _retry_available_at(job: GenerationJob, failure: dict | None) -> datetime | None:
    if not failure or failure["failure_kind"] != "rate_limited":
        return None
    delay = failure.get("retry_after_seconds")
    try:
        delay_seconds = int(delay)
    except (TypeError, ValueError):
        delay_seconds = DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
    delay_seconds = max(1, min(300, delay_seconds))
    updated_at = job.updated_at or utc_now()
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at + timedelta(seconds=delay_seconds)


def _latest_lesson_score(
    session: Session,
    lesson: PlanLesson,
    *,
    attempt_session_id: str | None = None,
) -> int | None:
    activities = _scored_activities(lesson)
    if not activities:
        return None
    latest_scores: list[int] = []
    for activity in activities:
        selected = (
            ActivityAttempt
            if activity["type"] == "pronunciation_drill"
            else ActivityAttempt.score
        )
        query = select(selected).where(
                ActivityAttempt.user_id == _user_id(),
                ActivityAttempt.lesson_id == lesson.id,
                ActivityAttempt.activity_id == activity["id"],
            )
        if attempt_session_id is not None:
            query = query.where(
                ActivityAttempt.response["attempt_session_id"].astext
                == attempt_session_id
            )
        latest = session.scalar(
            query.order_by(
                ActivityAttempt.created_at.desc(), ActivityAttempt.id.desc()
            ).limit(1)
        )
        if activity["type"] == "pronunciation_drill":
            attempt = latest
            score = attempt.score if attempt is not None else None
            if (
                attempt is not None
                and not isinstance((attempt.response or {}).get("pronunciation"), dict)
            ):
                # Before pronunciation checks became acoustic, Continue
                # created a synthetic 100. It is not a verified sound score.
                score = None
        else:
            score = latest
        # Keeping unanswered scored activities in the denominator prevents a
        # single correct item from displaying a misleading perfect lesson score.
        latest_scores.append(int(score) if score is not None else 0)
    return round(sum(latest_scores) / len(latest_scores))


def _activity_skill_ids(activity: dict, lesson: PlanLesson) -> list[str]:
    explicit = [
        item for item in activity.get("skill_ids", []) if item in lesson.skill_ids
    ]
    if explicit:
        return explicit
    if lesson.lesson_type != "assessment" or len(lesson.skill_ids) <= 1:
        return list(lesson.skill_ids)
    # Imported checkpoints may omit explicit activity-to-skill binding.
    # Curated checkpoints are assembled round-robin from the ordered skills.
    activities = _scored_activities(lesson)
    index = next(
        (position for position, item in enumerate(activities) if item["id"] == activity["id"]),
        0,
    )
    return [lesson.skill_ids[index % len(lesson.skill_ids)]]


def _eligible_pending_lesson_ids(
    session: Session, revision_id: uuid.UUID
) -> list[uuid.UUID]:
    owner_id = session.scalar(
        select(LearningPlan.user_id)
        .join(PlanRevision, PlanRevision.plan_id == LearningPlan.id)
        .where(PlanRevision.id == revision_id)
    )
    if owner_id is None:
        return []
    lessons = session.scalars(
        select(PlanLesson)
        .where(PlanLesson.revision_id == revision_id)
        .order_by(PlanLesson.week_sequence, PlanLesson.lesson_sequence)
    ).all()
    completed_ids = set(
        session.scalars(
            select(LessonProgress.lesson_id).where(
                LessonProgress.user_id == owner_id,
                LessonProgress.status == "completed",
                LessonProgress.lesson_id.in_([item.id for item in lessons]),
            )
        ).all()
    ) if lessons else set()
    completed_keys = {
        item.lesson_key for item in lessons if item.id in completed_ids
    }
    return [
        item.id
        for item in lessons
        if item.content_status == "pending"
        and set(item.required_lesson_keys or []).issubset(completed_keys)
    ]


def _verified_completed_activity_ids(
    session: Session,
    lesson: PlanLesson,
    progress: LessonProgress,
) -> list[str]:
    completed = list(progress.completed_activity_ids or [])
    pronunciation_activities = {
        activity["id"]: activity
        for activity in _scored_activities(lesson)
        if activity["type"] == "pronunciation_drill"
    }
    pronunciation_ids = set(pronunciation_activities)
    if not pronunciation_ids:
        return completed
    attempts = session.scalars(
        select(ActivityAttempt).where(
            ActivityAttempt.user_id == _user_id(),
            ActivityAttempt.lesson_id == lesson.id,
            ActivityAttempt.activity_id.in_(pronunciation_ids),
            ActivityAttempt.correct.is_(True),
        )
    ).all()
    verified = {
        activity_id
        for activity_id, activity in pronunciation_activities.items()
        if _pronunciation_activity_complete(
            activity,
            [attempt for attempt in attempts if attempt.activity_id == activity_id],
        )
    }
    return [
        activity_id
        for activity_id in completed
        if activity_id not in pronunciation_ids or activity_id in verified
    ]


def _required_pronunciation_targets(activity: dict) -> set[str]:
    return {
        _normalize_text_answer(_practice_item_text(item))
        for item in activity.get("data", {}).get("practice_items", [])
        if _normalize_text_answer(_practice_item_text(item))
    }


def _passed_pronunciation_targets(
    activity: dict,
    attempts: list[ActivityAttempt],
) -> set[str]:
    required = _required_pronunciation_targets(activity)
    return {
        normalized
        for attempt in attempts
        if attempt.correct is True
        and isinstance((attempt.response or {}).get("pronunciation"), dict)
        and (
            normalized := _normalize_text_answer(
                (attempt.response or {})["pronunciation"].get("target", "")
            )
        )
        in required
    }


def _pronunciation_activity_complete(
    activity: dict,
    attempts: list[ActivityAttempt],
) -> bool:
    required = _required_pronunciation_targets(activity)
    return bool(required) and required.issubset(
        _passed_pronunciation_targets(activity, attempts)
    )


def _progress_view(
    progress: LessonProgress,
    required_count: int,
    *,
    completed_activity_ids: list[str] | None = None,
    best_score: int | None = None,
) -> LessonProgressView:
    visible_completed_ids = (
        list(progress.completed_activity_ids or [])
        if completed_activity_ids is None
        else list(completed_activity_ids)
    )
    fraction = 1.0 if progress.status == "completed" else (
        min(1.0, len(visible_completed_ids) / required_count)
        if required_count else 0.0
    )
    return LessonProgressView(
        status=progress.status,
        progress_fraction=fraction,
        best_score=progress.best_score if best_score is None else best_score,
        attempts=progress.attempts,
        completed_activity_ids=visible_completed_ids,
        completed_at=progress.completed_at,
    )


def _learner_today(offset_minutes: int = 0) -> date:
    bounded_offset = max(-720, min(840, int(offset_minutes)))
    return (utc_now() + timedelta(minutes=bounded_offset)).date()


def _current_streak(values: list[date], *, today: date | None = None) -> int:
    dates = set(values)
    cursor = today or utc_now().date()
    if cursor not in dates and cursor - timedelta(days=1) in dates:
        cursor -= timedelta(days=1)
    count = 0
    while cursor in dates:
        count += 1
        cursor -= timedelta(days=1)
    return count


def _longest_streak(values: list[date]) -> int:
    longest = current = 0
    previous = None
    for value in sorted(set(values)):
        current = current + 1 if previous and value == previous + timedelta(days=1) else 1
        longest = max(longest, current)
        previous = value
    return longest


def _proposal_view(item: AdaptationProposal) -> AdaptationProposalView:
    return AdaptationProposalView(
        id=item.id,
        status=item.status,
        summary=item.summary,
        changes=item.changes,
        evidence=item.evidence,
        created_at=item.created_at,
    )


def _roleplay_session_view(item: RoleplaySession) -> RoleplaySessionView:
    return RoleplaySessionView(
        id=item.id,
        client_session_id=item.client_session_id,
        scenario_id=item.scenario_id,
        cefr_level=item.cefr_level,
        scenario=item.scenario,
        status=item.status,
        duration_seconds=item.duration_seconds,
        message_count=item.message_count,
        successful_turns=item.successful_turns,
        spoken_word_count=item.spoken_word_count,
        voiced_seconds=item.voiced_seconds,
        alignment_coverage=item.alignment_coverage,
        average_word_confidence=item.average_word_confidence,
        average_fluency=item.average_fluency,
        average_prosody=item.average_prosody,
        review_words=item.review_words,
        objective_state=item.objective_state,
        evaluation=item.evaluation,
        ended_reason=item.ended_reason,
        ended_at=item.ended_at,
        created_at=item.created_at,
    )


def _roleplay_turn_dict(item: RoleplayTurn) -> dict:
    return {
        "turn_id": item.turn_id,
        "sequence": item.sequence,
        "input_mode": item.input_mode,
        "user_text": item.user_text,
        "assistant_text": item.assistant_text,
        "grammar_corrected_text": item.grammar_corrected_text,
        "grammar_feedback": item.grammar_feedback,
        "grammar_error_units": item.grammar_error_units,
        "word_count": item.word_count,
        "word_feedback": copy.deepcopy(item.word_feedback or []),
        "delivery_metrics": copy.deepcopy(item.delivery_metrics or {}),
        "objective_evidence": copy.deepcopy(item.objective_evidence or []),
        "created_at": item.created_at,
    }
