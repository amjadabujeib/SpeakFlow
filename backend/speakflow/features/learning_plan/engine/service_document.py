"""Generation views, active documents, and lesson completion assembly."""

from __future__ import annotations

import copy
import math
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .curated_lessons import get_curated_template
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt,
    CurriculumSource,
    GenerationJob,
    LearningPlan,
    LessonProgress,
    PlanLesson,
    PlanRevision,
    StudyDay,
    utc_now,
)
from .schemas import GenerationView, PlpDocument
from .service_errors import PlpInvalidAttemptError, PlpNotFoundError
from .service_grading import (
    _decode_job_failure,
    _required_activities,
    _sanitize_content,
)
from .service_progress import (
    _current_streak,
    _latest_lesson_score,
    _learner_today,
    _longest_streak,
    _progress_view,
    _pronunciation_activity_progress,
    _retry_available_at,
    _verified_completed_activity_ids,
    _visible_lesson_status,
)
from .standard import PLP_FORMAT_REVISION


class PlpDocumentMixin:
    def _generation_view(self, session: Session, job: GenerationJob) -> GenerationView:
        lessons = session.scalars(
            select(PlanLesson).where(PlanLesson.revision_id == job.revision_id)
        ).all()
        ready_by_week = defaultdict(int)
        total_by_week = defaultdict(int)
        for lesson in lessons:
            total_by_week[lesson.week_sequence] += 1
            if lesson.content_status == "ready":
                ready_by_week[lesson.week_sequence] += 1
        ready_weeks = 0
        for week in range(1, 5):
            if total_by_week[week] and ready_by_week[week] == total_by_week[week]:
                ready_weeks += 1
            else:
                break
        failure = _decode_job_failure(job.error)
        retry_available_at = _retry_available_at(job, failure)
        retry_after_seconds = 0
        if retry_available_at is not None:
            retry_after_seconds = max(
                0,
                math.ceil((retry_available_at - utc_now()).total_seconds()),
            )
        return GenerationView(
            job_id=job.id,
            status=job.status,
            ready_weeks=ready_weeks,
            completed_lessons=sum(ready_by_week.values()),
            total_lessons=len(lessons),
            failed_lesson_ids=[
                lesson.lesson_key
                for lesson in lessons
                if lesson.content_status == "failed"
            ],
            error=failure["message"] if failure else None,
            failure_kind=failure["failure_kind"] if failure else None,
            retry_available_at=retry_available_at,
            retry_after_seconds=retry_after_seconds,
        )

    def _build_document(
        self,
        session: Session,
        plan: LearningPlan,
        revision: PlanRevision,
        job: GenerationJob,
    ) -> PlpDocument:
        lessons = session.scalars(
            select(PlanLesson)
            .where(PlanLesson.revision_id == revision.id)
            .order_by(PlanLesson.week_sequence, PlanLesson.lesson_sequence)
        ).all()
        lesson_by_key = {item.lesson_key: item for item in lessons}
        plan_json = copy.deepcopy(revision.outline)
        plan_json["id"] = str(plan.id)
        plan_json["revision"] = revision.revision
        for week in plan_json["weeks"]:
            for unit in week["units"]:
                rendered = []
                for shell in unit["lessons"]:
                    lesson = lesson_by_key[shell["lesson_key"]]
                    generated = lesson.content or {}
                    provenance = generated.get("provenance", {})
                    origin = provenance.get("origin")
                    review_status = provenance.get("review_status")
                    if origin not in {"curated", "retrieval_generated"}:
                        origin = "retrieval_generated"
                    if review_status not in {"reviewed", "generated_validated"}:
                        review_status = (
                            "reviewed" if origin == "curated" else "generated_validated"
                        )
                    rendered.append(
                        {
                            "id": lesson.lesson_key,
                            "sequence": lesson.lesson_sequence,
                            "type": lesson.lesson_type,
                            "title": generated.get(
                                "title", shell["specification"]["title"]
                            ),
                            "description": generated.get(
                                "description", shell["specification"]["description"]
                            ),
                            "estimated_minutes": lesson.estimated_minutes,
                            "xp": lesson.xp,
                            "completion_policy": shell["specification"][
                                "completion_policy"
                            ],
                            "objectives": shell["specification"]["objectives"],
                            "skill_ids": lesson.skill_ids,
                            "required_lesson_ids": lesson.required_lesson_keys,
                            "personalization_reason": shell["specification"][
                                "personalization_reason"
                            ],
                            "lesson_role": shell["specification"].get("lesson_role"),
                            "can_do_statement": shell["specification"].get("can_do"),
                            "content_instance_id": generated.get("content_instance_id"),
                            "grounding": {
                                "origin": origin,
                                "review_status": (
                                    review_status
                                    if lesson.content_status == "ready"
                                    else lesson.content_status
                                ),
                                "retrieval_tags": [
                                    f"cefr:{shell['specification']['cefr_level']}",
                                    *[f"skill:{item}" for item in lesson.skill_ids],
                                ],
                                "source_refs": lesson.source_refs,
                                "source_chunks": provenance.get("source_chunks", []),
                                "provider": provenance.get("provider"),
                                "model": provenance.get("model"),
                            },
                            "content_status": lesson.content_status,
                            "content": (
                                _sanitize_content(
                                    generated.get("content"),
                                    reviewed_template=(
                                        get_curated_template(
                                            shell["specification"]["cefr_level"],
                                            lesson.lesson_type,
                                        )
                                        if "project_core_a1_b2_v1" in lesson.source_refs
                                        and lesson.lesson_type != "assessment"
                                        else None
                                    ),
                                )
                                if lesson.content_status == "ready"
                                else None
                            ),
                        }
                    )
                unit["lessons"] = rendered

        progress_rows = session.scalars(
            select(LessonProgress)
            .join(PlanLesson, LessonProgress.lesson_id == PlanLesson.id)
            .where(
                LessonProgress.user_id == _user_id(),
                PlanLesson.revision_id == revision.id,
            )
        ).all()
        progress_by_lesson_id = {item.lesson_id: item for item in progress_rows}
        visible_completed_by_lesson_id = {}
        visible_status_by_lesson_id = {}
        for lesson in lessons:
            row = progress_by_lesson_id.get(lesson.id)
            if row is None:
                continue
            visible_completed = _verified_completed_activity_ids(
                session,
                lesson,
                row,
            )
            visible_completed_by_lesson_id[lesson.id] = visible_completed
            visible_status_by_lesson_id[lesson.id] = _visible_lesson_status(
                row,
                _required_activities(lesson),
                visible_completed,
            )
        ready_lessons = [item for item in lessons if item.content_status == "ready"]
        current = next(
            (
                item
                for item in ready_lessons
                if progress_by_lesson_id.get(item.id) is None
                or visible_status_by_lesson_id[item.id] != "completed"
            ),
            None,
        )
        states = {}
        for lesson in lessons:
            row = progress_by_lesson_id.get(lesson.id)
            if row is None:
                if current is not None and lesson.id == current.id:
                    states[lesson.lesson_key] = {
                        "status": "in_progress",
                        "progress_fraction": 0,
                        "best_score": None,
                        "attempts": 0,
                        "completed_at": None,
                    }
                continue
            verified_completed_ids = visible_completed_by_lesson_id[lesson.id]
            has_unverified_legacy_pronunciation = verified_completed_ids != list(
                row.completed_activity_ids or []
            )
            states[lesson.lesson_key] = _progress_view(
                row,
                len(_required_activities(lesson)),
                completed_activity_ids=verified_completed_ids,
                best_score=(
                    _latest_lesson_score(session, lesson)
                    if has_unverified_legacy_pronunciation
                    else None
                ),
                pronunciation_activity_progress=(
                    _pronunciation_activity_progress(session, lesson)
                ),
                status=visible_status_by_lesson_id[lesson.id],
            ).model_dump(mode="json")
        learner_today = _learner_today(
            int(revision.learner_snapshot.get("timezone_offset_minutes") or 0)
        )
        study_dates = session.scalars(
            select(StudyDay.studied_on)
            .where(
                StudyDay.user_id == _user_id(),
                StudyDay.studied_on
                >= learner_today - timedelta(days=learner_today.weekday()),
            )
            .order_by(StudyDay.studied_on)
        ).all()
        source_ids = sorted(
            {source for lesson in lessons for source in lesson.source_refs}
        )
        sources = (
            session.scalars(
                select(CurriculumSource).where(CurriculumSource.id.in_(source_ids))
            ).all()
            if source_ids
            else []
        )
        return PlpDocument.model_validate(
            {
                "format_revision": PLP_FORMAT_REVISION,
                "generation": self._generation_view(session, job).model_dump(
                    mode="json"
                ),
                "plan": plan_json,
                "learner_snapshot": revision.learner_snapshot,
                "progress": {
                    "current_lesson_id": current.lesson_key if current else None,
                    "current_streak_days": _current_streak(
                        study_dates,
                        today=learner_today,
                    ),
                    "longest_streak_days": _longest_streak(
                        session.scalars(
                            select(StudyDay.studied_on)
                            .where(StudyDay.user_id == _user_id())
                            .order_by(StudyDay.studied_on)
                        ).all()
                    ),
                    "weekly_goal_days": plan_json["schedule"]["days_per_week"],
                    "studied_dates_this_week": [
                        item.isoformat() for item in study_dates
                    ],
                    "lesson_states": states,
                },
                "knowledge_sources": [
                    {
                        "id": source.id,
                        "title": source.title,
                        "locator": source.locator,
                        "license": source.license,
                        "version": source.version,
                    }
                    for source in sources
                ],
            }
        )

    def _find_active_lesson_by_activity(
        self, session: Session, activity_id: str
    ) -> PlanLesson:
        plan = self._active_plan(session)
        if plan is None or plan.active_revision_id is None:
            raise PlpNotFoundError("no active plan")
        lessons = session.scalars(
            select(PlanLesson).where(
                PlanLesson.revision_id == plan.active_revision_id,
                PlanLesson.content_status == "ready",
            )
        ).all()
        for lesson in lessons:
            if any(
                item.get("id") == activity_id
                for item in (lesson.content or {})
                .get("content", {})
                .get("activities", [])
            ):
                return lesson
        raise PlpNotFoundError("activity was not found in the active plan")

    def _update_lesson_completion(
        self,
        session: Session,
        lesson: PlanLesson,
        progress: LessonProgress,
        *,
        attempt_session_id: str | None = None,
    ) -> bool:
        required_ids = _required_activities(lesson)
        if not set(required_ids).issubset(progress.completed_activity_ids):
            return False
        if lesson.lesson_type == "assessment":
            if not attempt_session_id:
                raise PlpInvalidAttemptError(
                    "checkpoint attempts require an attempt_session_id"
                )
            attempted_this_session = set(
                session.scalars(
                    select(ActivityAttempt.activity_id).where(
                        ActivityAttempt.user_id == _user_id(),
                        ActivityAttempt.lesson_id == lesson.id,
                        ActivityAttempt.response["attempt_session_id"].astext
                        == attempt_session_id,
                    )
                ).all()
            )
            if not set(required_ids).issubset(attempted_this_session):
                return False
            final_score = (
                _latest_lesson_score(
                    session,
                    lesson,
                    attempt_session_id=attempt_session_id,
                )
                or 0
            )
            progress.best_score = max(progress.best_score or 0, final_score)
            minimum_score = int(
                lesson.specification.get("completion_policy", {}).get(
                    "minimum_score", 75
                )
            )
            if final_score < minimum_score:
                return False
        progress.status = "completed"
        progress.completed_at = progress.completed_at or utc_now()
        return True

    @staticmethod
    def _active_plan(session: Session) -> LearningPlan | None:
        return session.scalar(
            select(LearningPlan)
            .where(
                LearningPlan.user_id == _user_id(),
                LearningPlan.active_revision_id.is_not(None),
            )
            .order_by(LearningPlan.created_at.desc())
        )
