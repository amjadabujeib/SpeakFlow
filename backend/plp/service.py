from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
import unicodedata
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import (
    GENERATOR_VERSION,
    PLANNER_VERSION,
)
from .identity import current_user_id as _user_id
from .curated_lessons import get_curated_template
from .database import check_database, session_scope
from .generator import GenerationError, LessonGenerator
from .learner_glosses import reviewed_learner_gloss
from .models import (
    ActivityAttempt,
    AdaptationProposal,
    CurriculumSource,
    GenerationJob,
    LearnerProfile,
    LearningPlan,
    LessonProgress,
    PlanLesson,
    PlanRevision,
    RoleplayScenario,
    RoleplaySession,
    RoleplayTurn,
    Skill,
    SkillEvidence,
    SkillPrerequisite,
    StudyDay,
    User,
    utc_now,
)
from .planner import PlanningSkill, build_outline
from .retrieval import CurriculumRetriever, RetrievalError
from .schemas import (
    ActivityAttemptInput,
    ActivityAttemptResult,
    AdaptationProposalView,
    GenerationAccepted,
    GenerationView,
    LearnerProfileInput,
    LearnerProfileView,
    LessonProgressView,
    PlpDocumentV2,
    RoleplaySessionStart,
    RoleplaySessionStartView,
    RoleplaySessionView,
    RoleplayTranscriptView,
    RoleplayScenarioCreate,
    RoleplayScenarioView,
    RoleplayTurnInput,
)
from .weekly_mission import WeeklyMissionGenerator
from roleplay_engine import (
    apply_objective_updates,
    builtin_scenarios,
    custom_scenario_definition,
    get_builtin_scenario,
    initial_objective_state,
)


JOB_LEASE_SECONDS = 120
FAILURE_ENVELOPE_PREFIX = "__plp_failure_v1__:"
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 90
PRONUNCIATION_PASS_ACCURACY = 85
PRONUNCIATION_PASS_COMPLETENESS = 90


class PlpUnavailableError(RuntimeError):
    pass


class PlpNotFoundError(RuntimeError):
    pass


class PlpConflictError(RuntimeError):
    pass


class PlpInvalidAttemptError(RuntimeError):
    pass


class PlpService:
    def __init__(self) -> None:
        self.retriever = CurriculumRetriever()
        self.generator = LessonGenerator()
        self.weekly_generator = WeeklyMissionGenerator(self.generator)
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_worker(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="plp-generation-worker", daemon=True
        )
        self._worker_thread.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=3)

    def health(self) -> dict:
        try:
            check_database()
            return {"database": "ready", "worker": self._worker_thread is not None and self._worker_thread.is_alive()}
        except Exception as exc:
            return {"database": "unavailable", "worker": False, "error": str(exc)}

    def save_profile(self, profile_data: LearnerProfileInput) -> LearnerProfileView:
        try:
            with session_scope() as session:
                _ensure_local_user(session)
                profile = session.get(LearnerProfile, _user_id())
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

    def list_roleplay_scenarios(self) -> list[RoleplayScenarioView]:
        try:
            with session_scope() as session:
                custom_rows = session.scalars(
                    select(RoleplayScenario)
                    .where(RoleplayScenario.user_id == _user_id())
                    .order_by(RoleplayScenario.created_at)
                ).all()
                values = [
                    {**item, "custom": False} for item in builtin_scenarios()
                ]
                values.extend(
                    {**copy.deepcopy(row.definition), "custom": True}
                    for row in custom_rows
                )
                return [RoleplayScenarioView.model_validate(item) for item in values]
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def create_roleplay_scenario(
        self, payload: RoleplayScenarioCreate
    ) -> RoleplayScenarioView:
        try:
            with session_scope() as session:
                _ensure_local_user(session)
                scenario_id = f"custom_{uuid.uuid4().hex[:20]}"
                definition = custom_scenario_definition(
                    scenario_id=scenario_id,
                    category=payload.category,
                    title=payload.title,
                    description=payload.description,
                    designed_cefr_level=payload.designed_cefr_level,
                )
                if payload.ai_role is not None:
                    definition.update(
                        {
                            "icon": payload.icon,
                            "ai_role": payload.ai_role,
                            "learner_role": payload.learner_role,
                            "opening": payload.opening,
                            "objectives": [
                                item.model_dump() for item in payload.objectives or []
                            ],
                            "target_language": list(payload.target_language or []),
                            "evaluation_rubric": [
                                item.model_dump()
                                for item in payload.evaluation_rubric or []
                            ],
                            "designed_cefr_level": payload.designed_cefr_level,
                        }
                    )
                validated = RoleplayScenarioView.model_validate(
                    {**definition, "custom": True}
                )
                definition = validated.model_dump(exclude={"custom"})
                row = RoleplayScenario(
                    id=scenario_id,
                    user_id=_user_id(),
                    category=definition["category"],
                    title=definition["title"],
                    description=definition["description"],
                    definition=definition,
                    version=1,
                )
                session.add(row)
                session.flush()
                return RoleplayScenarioView.model_validate(
                    {**definition, "custom": True}
                )
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

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
                        scenario_version=int(scenario.get("version", 1)),
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
                row.successful_turns = sequence
                row.objective_state = apply_objective_updates(
                    row.objective_state,
                    objective_updates,
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
                evidence = evaluation.get("evidence", {})
                successful_turns = int(evidence.get("successful_turns") or 0)
                row.status = "complete" if successful_turns > 0 else "abandoned"
                row.ended_reason = ended_reason
                row.ended_at = now
                started = row.created_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                row.duration_seconds = max(
                    0, min(21600, int((now - started).total_seconds()))
                )
                row.evaluation = {
                    **copy.deepcopy(evaluation),
                    "corrections": copy.deepcopy(corrections),
                }
                row.evaluation_version = evaluation.get("evaluation_version")
                scores = evaluation.get("scores", {})
                row.successful_turns = successful_turns
                row.spoken_word_count = int(evidence.get("spoken_word_count") or 0)
                row.voiced_seconds = float(evidence.get("voiced_seconds") or 0)
                row.alignment_coverage = evidence.get("alignment_coverage")
                row.average_word_confidence = scores.get("intelligibility_proxy")
                row.average_fluency = scores.get("delivery_fluency")
                row.average_prosody = scores.get("pitch_variation")
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

    def create_generation(self, *, reason: str = "onboarding") -> GenerationAccepted:
        try:
            with session_scope() as session:
                profile = session.get(LearnerProfile, _user_id())
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
                priority_skill_ids: list[str] = []
                if reason.startswith("adaptation:"):
                    proposal_id = uuid.UUID(reason.split(":", 1)[1])
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
                    )
                    if proposal is None:
                        raise PlpNotFoundError("adaptation proposal was not found")
                    base_revision = session.get(PlanRevision, proposal.base_revision_id)
                    priority_skill_ids = [
                        change["skill_id"]
                        for change in proposal.changes
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
                    planner_version=PLANNER_VERSION,
                    generator_version=GENERATOR_VERSION,
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
                plan.active_revision_id = revision.id
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

    def get_active_document(self) -> PlpDocumentV2:
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
                session.merge(StudyDay(user_id=_user_id(), studied_on=date.today()))
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
                )
                if proposal is None:
                    raise PlpNotFoundError("adaptation proposal was not found")
                if proposal.status != "pending":
                    raise PlpConflictError("adaptation proposal has already been decided")
                if not approve:
                    proposal.status = "rejected"
                    proposal.decided_at = utc_now()
            if not approve:
                return {"status": "rejected", "proposal_id": str(proposal_id)}
            generation = self.create_generation(reason=f"adaptation:{proposal_id}")
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
                )
                assert proposal is not None
                proposal.status = "approved"
                proposal.decided_at = utc_now()
            return {
                "status": "approved",
                "proposal_id": str(proposal_id),
                "generation": generation.model_dump(mode="json"),
            }
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

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
        except SQLAlchemyError:
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
            is_mission_v3 = bool(
                first_eligible
                and first_eligible.specification.get("architecture") == "mission_v3"
            )
            mission_week = first_eligible.week_sequence if first_eligible else None
            if is_mission_v3:
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
        if is_mission_v3:
            try:
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
            # Retained v2 revisions still use their original per-lesson path.
            batch_limit = 4 if self.generator.provider == "curated" else 1
            for lesson_id in eligible_ids[:batch_limit]:
                if self._stop_event.is_set():
                    return
                try:
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
            if lesson is not None and lesson.specification.get("architecture") == "mission_v3":
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
                if lesson.specification.get("architecture") == "mission_v3":
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

    def _generate_lesson(self, job_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
        # Commit the attempt before any embedding/network work. A generation
        # failure must never roll this counter back into an infinite loop.
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            lesson = session.get(PlanLesson, lesson_id)
            if job is None or lesson is None or lesson.content_status == "ready":
                return
            revision = session.get(PlanRevision, lesson.revision_id)
            assert revision is not None
            support_language = revision.learner_snapshot.get("support_language")
            lesson.generation_attempts += 1
            lesson.generation_error = None
            job.updated_at = utc_now()
            specification = copy.deepcopy(lesson.specification)
            lesson_type = lesson.lesson_type
            skill_ids = list(lesson.skill_ids)
            lesson_key = lesson.lesson_key

        with session_scope() as session:
            if lesson_type == "assessment":
                # Retrieve each assessed skill, then deduplicate.
                chunks_by_id = {}
                for skill_id in skill_ids:
                    for chunk in self.retriever.retrieve(
                        session,
                        query=f"{specification['title']} {skill_id}",
                        cefr_level=specification["cefr_level"],
                        skill_ids=[skill_id],
                        limit=3,
                    ):
                        chunks_by_id[chunk.id] = chunk
                chunks = list(chunks_by_id.values())[:8]
            else:
                chunks = self.retriever.retrieve(
                    session,
                    query=(
                        f"{specification['title']} {specification['description']} "
                        f"{' '.join(specification.get('topics', []))}"
                    ),
                    cefr_level=specification["cefr_level"],
                    skill_ids=skill_ids,
                )
        generated, source_refs = self.generator.generate(
            specification=specification,
            lesson_key=lesson_key,
            chunks=chunks,
            support_language=support_language,
        )

        with session_scope() as session:
            lesson = session.get(PlanLesson, lesson_id)
            if lesson is None:
                return
            lesson.content = generated
            lesson.source_refs = source_refs
            lesson.content_status = "ready"
            lesson.generation_error = None

    def _generate_week(self, job_id: uuid.UUID, week_sequence: int) -> None:
        """Generate and persist one complete v3 cohort after one writer call."""
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            revision_id = job.revision_id
            revision = session.get(PlanRevision, revision_id)
            assert revision is not None
            lessons = session.scalars(
                select(PlanLesson)
                .where(
                    PlanLesson.revision_id == revision_id,
                    PlanLesson.week_sequence == week_sequence,
                )
                .order_by(PlanLesson.lesson_sequence)
            ).all()
            if len(lessons) != 5:
                raise GenerationError(
                    f"mission week {week_sequence} must contain exactly five lessons"
                )
            if all(lesson.content_status == "ready" for lesson in lessons):
                return
            if any(lesson.content_status == "ready" for lesson in lessons):
                raise GenerationError(
                    "a mission cohort is partially ready; refusing to overwrite immutable content"
                )
            prior_attempts = {lesson.generation_attempts for lesson in lessons}
            if len(prior_attempts) != 1:
                raise GenerationError(
                    "mission cohort generation attempts diverged; refusing an ambiguous retry"
                )
            for lesson in lessons:
                lesson.generation_attempts += 1
                lesson.generation_error = None
            generation_attempt = next(iter(prior_attempts)) + 1
            job.updated_at = utc_now()
            support_language = revision.learner_snapshot.get("support_language")
            level = lessons[0].specification["cefr_level"]
            selected_interest = lessons[0].specification.get("interest", {}).get(
                "label"
            )
            interests = [selected_interest] if selected_interest else []
            first_specification = lessons[0].specification
            scenario = first_specification.get("scenario", {})
            palette_query = " ".join(
                [
                    f"{level} English vocabulary for {selected_interest or 'general English'}.",
                    f"Scenario: {scenario.get('title', '')}.",
                    f"Learner task: {first_specification.get('can_do', '')}.",
                    "Setting: "
                    + ", ".join(scenario.get("setting_slots", []))
                    + ".",
                    "Lesson domains: "
                    + ", ".join(
                        dict.fromkeys(lesson.lesson_type for lesson in lessons)
                    )
                    + ".",
                ]
            )
            palette_seed = (
                f"{lessons[0].specification.get('variation_seed', 'default')}:"
                f"{week_sequence}:{generation_attempt}"
            )
            skill_ids = list(dict.fromkeys(
                skill_id for lesson in lessons for skill_id in lesson.skill_ids
            ))
            lesson_shells = [
                {
                    "lesson_key": lesson.lesson_key,
                    "sequence": lesson.lesson_sequence,
                    "week_sequence": lesson.week_sequence,
                    "type": lesson.lesson_type,
                    "skill_ids": list(lesson.skill_ids),
                    "specification": copy.deepcopy(lesson.specification),
                }
                for lesson in lessons
            ]
            used_concept_ids: set[str] = set()
            used_concept_terms: set[str] = set()
            ready_contents = session.scalars(
                select(PlanLesson.content).where(
                    PlanLesson.revision_id == revision_id,
                    PlanLesson.content_status == "ready",
                )
            ).all()
            for content in ready_contents:
                writer_request = (content or {}).get("provenance", {}).get(
                    "writer_request", {}
                )
                for target in writer_request.get("prototype_targets", []):
                    concept_id = target.get("concept_id")
                    if concept_id:
                        used_concept_ids.add(concept_id)
                    term = target.get("term")
                    if isinstance(term, str) and term.strip():
                        used_concept_terms.add(term.strip().casefold())

        with session_scope() as session:
            chunks = self.retriever.retrieve_exact(
                session,
                cefr_level=level,
                skill_ids=skill_ids,
            )
            lexical_palette = self.retriever.retrieve_lexical_palette(
                session,
                cefr_level=level,
                interests=interests,
                seed=palette_seed,
                limit=2,
                exclude_ids=used_concept_ids,
                exclude_terms=used_concept_terms,
                query_text=palette_query,
            )
        generated = self.weekly_generator.generate(
            lessons=lesson_shells,
            chunks=chunks,
            lexical_palette=lexical_palette,
            support_language=support_language,
            generation_attempt=generation_attempt,
        )
        if set(generated) != {item["lesson_key"] for item in lesson_shells}:
            raise GenerationError("weekly compiler returned an incomplete lesson cohort")

        # One transaction makes the cohort immutable and prevents a half-week
        # from becoming visible if persistence or validation fails.
        with session_scope() as session:
            lessons = session.scalars(
                select(PlanLesson)
                .where(
                    PlanLesson.revision_id == revision_id,
                    PlanLesson.week_sequence == week_sequence,
                )
                .order_by(PlanLesson.lesson_sequence)
                .with_for_update()
            ).all()
            if any(lesson.content_status == "ready" for lesson in lessons):
                raise GenerationError(
                    "mission cohort changed during generation; refusing to overwrite it"
                )
            for lesson in lessons:
                payload, source_refs = generated[lesson.lesson_key]
                lesson.content = payload
                lesson.source_refs = source_refs
                lesson.content_status = "ready"
                lesson.generation_error = None

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
                lesson.lesson_key for lesson in lessons if lesson.content_status == "failed"
            ],
            error=failure["message"] if failure else None,
            failure_kind=failure["failure_kind"] if failure else None,
            retry_available_at=retry_available_at,
            retry_after_seconds=retry_after_seconds,
        )

    def _build_document(
        self, session: Session, plan: LearningPlan, revision: PlanRevision, job: GenerationJob
    ) -> PlpDocumentV2:
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
                        # Stored v2 data predating explicit provenance remains
                        # readable, but new content never relies on a version
                        # prefix to claim human review.
                        legacy_version = str(generated.get("generator_version", ""))
                        origin = (
                            "curated"
                            if "curated" in legacy_version
                            else "retrieval_generated"
                        )
                    if review_status not in {"reviewed", "generated_validated"}:
                        review_status = (
                            "reviewed" if origin == "curated" else "generated_validated"
                        )
                    rendered.append(
                        {
                            "id": lesson.lesson_key,
                            "sequence": lesson.lesson_sequence,
                            "type": lesson.lesson_type,
                            "title": generated.get("title", shell["specification"]["title"]),
                            "description": generated.get("description", shell["specification"]["description"]),
                            "estimated_minutes": lesson.estimated_minutes,
                            "xp": lesson.xp,
                            "completion_policy": shell["specification"]["completion_policy"],
                            "objectives": shell["specification"]["objectives"],
                            "skill_ids": lesson.skill_ids,
                            "required_lesson_ids": lesson.required_lesson_keys,
                            "personalization_reason": shell["specification"]["personalization_reason"],
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
                                        if "project_core_a1_b2_v1"
                                        in lesson.source_refs
                                        and lesson.lesson_type != "assessment"
                                        else None
                                    ),
                                )
                                if lesson.content_status == "ready" else None
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
        ready_lessons = [item for item in lessons if item.content_status == "ready"]
        current = next(
            (
                item for item in ready_lessons
                if progress_by_lesson_id.get(item.id) is None or
                progress_by_lesson_id[item.id].status != "completed"
            ),
            None,
        )
        states = {}
        for lesson in lessons:
            row = progress_by_lesson_id.get(lesson.id)
            if row is None:
                if current is not None and lesson.id == current.id:
                    states[lesson.lesson_key] = {
                        "status": "in_progress", "progress_fraction": 0,
                        "best_score": None, "attempts": 0, "completed_at": None,
                    }
                continue
            verified_completed_ids = _verified_completed_activity_ids(
                session,
                lesson,
                row,
            )
            has_unverified_legacy_pronunciation = (
                verified_completed_ids != list(row.completed_activity_ids or [])
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
            ).model_dump(mode="json")
        study_dates = session.scalars(
            select(StudyDay.studied_on)
            .where(
                StudyDay.user_id == _user_id(),
                StudyDay.studied_on >= date.today() - timedelta(days=date.today().weekday()),
            )
            .order_by(StudyDay.studied_on)
        ).all()
        source_ids = sorted({source for lesson in lessons for source in lesson.source_refs})
        sources = session.scalars(
            select(CurriculumSource).where(CurriculumSource.id.in_(source_ids))
        ).all() if source_ids else []
        return PlpDocumentV2.model_validate(
            {
                "schema_version": 2,
                "generation": self._generation_view(session, job).model_dump(mode="json"),
                "plan": plan_json,
                "learner_snapshot": revision.learner_snapshot,
                "progress": {
                    "current_lesson_id": current.lesson_key if current else None,
                    "current_streak_days": _current_streak(study_dates),
                    "longest_streak_days": _longest_streak(
                        session.scalars(
                            select(StudyDay.studied_on)
                            .where(StudyDay.user_id == _user_id())
                            .order_by(StudyDay.studied_on)
                        ).all()
                    ),
                    "weekly_goal_days": plan_json["schedule"]["days_per_week"],
                    "studied_dates_this_week": [item.isoformat() for item in study_dates],
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

    def _find_active_lesson_by_activity(self, session: Session, activity_id: str) -> PlanLesson:
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
                for item in (lesson.content or {}).get("content", {}).get("activities", [])
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
            final_score = _latest_lesson_score(
                session,
                lesson,
                attempt_session_id=attempt_session_id,
            ) or 0
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


plp_service = PlpService()


def _profile_input(profile: LearnerProfile) -> LearnerProfileInput:
    return LearnerProfileInput.model_validate(
        {
            "cefr_level": profile.cefr_level,
            "native_language": profile.native_language,
            "learning_goals": profile.learning_goals,
            "interests": profile.interests,
        }
    )


def _ensure_local_user(session: Session) -> None:
    if session.get(User, _user_id()) is None:
        session.add(User(id=_user_id(), kind="local_guest"))
        # These mappings deliberately avoid ORM relationships, so force the
        # parent row to exist before inserting its foreign-key-dependent
        # profile in the same transaction.
        session.flush()


def _profile_view(profile: LearnerProfile) -> LearnerProfileView:
    return LearnerProfileView(
        user_id=profile.user_id,
        revision=profile.revision,
        updated_at=profile.updated_at,
        **_profile_input(profile).model_dump(),
    )


def _learner_snapshot(profile: LearnerProfile) -> dict:
    return {
        "native_language": profile.native_language,
        "support_language": profile.support_language,
        "learning_goals": profile.learning_goals,
        "interests": profile.interests,
        "preferred_contexts": profile.preferred_contexts,
        "accent_preference": profile.accent_preference,
        "pronunciation_priorities": profile.pronunciation_priorities,
    }


def _database_error(exc: Exception) -> PlpUnavailableError:
    return PlpUnavailableError(
        "PLP PostgreSQL is unavailable. Start the configured database and run Alembic migrations. "
        f"Details: {exc}"
    )


def _unexpected_worker_error(exc: Exception) -> str:
    detail = " ".join(str(exc).split())[:700]
    return (
        f"Unexpected PLP worker failure ({type(exc).__name__}). "
        f"{detail or 'Check the backend log for details.'}"
    )


def _sanitize_content(
    content: dict | None,
    *,
    reviewed_template: dict | None = None,
) -> dict | None:
    if content is None:
        return None
    result = copy.deepcopy(content)
    if reviewed_template is not None:
        reviewed_fills = {
            tuple(
                sorted(
                    _normalize_text_answer(answer)
                    for answer in activity["data"]["accepted_answers"]
                )
            ): activity["data"]
            for activity in reviewed_template.get("activities", [])
            if activity.get("type") == "fill_blank"
        }
        for activity in result.get("activities", []):
            if activity.get("type") != "fill_blank":
                continue
            data = activity.get("data", {})
            answer_key = tuple(
                sorted(
                    _normalize_text_answer(answer)
                    for answer in data.get("accepted_answers", [])
                )
            )
            reviewed = reviewed_fills.get(answer_key)
            if reviewed is not None:
                data["prompt"] = reviewed["prompt"]
                data["explanation"] = reviewed["explanation"]
    for activity in result.get("activities", []):
        data = activity.get("data", {})
        if activity["type"] == "vocabulary_card":
            reviewed_gloss = reviewed_learner_gloss(
                str(data.get("word", "")),
                str(data.get("part_of_speech", "")) or None,
            )
            if reviewed_gloss is not None:
                # Repairs already-persisted prototype packs that predate the
                # learner-definition contract without mutating immutable
                # generated content or its original source provenance.
                data.setdefault("source_definition", data.get("definition"))
                data["definition"] = reviewed_gloss
                data["definition_origin"] = "reviewed_project_gloss"
            # Early prototype packs stored the curriculum-concept identity in
            # source_refs. A concept is content provenance, not a
            # CurriculumSource, so expose it in the card data and keep
            # source_refs closed over the public knowledge_sources registry.
            refs = activity.get("source_refs", [])
            concept_refs = [
                ref.removeprefix("concept:")
                for ref in refs
                if ref.startswith("concept:")
            ]
            if concept_refs and not data.get("concept_id"):
                data["concept_id"] = concept_refs[0]
            activity["source_refs"] = [
                ref for ref in refs if not ref.startswith("concept:")
            ]
        elif activity["type"] == "multiple_choice":
            data.pop("correct_option_id", None)
            data["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] == "fill_blank":
            data.pop("accepted_answers", None)
            data["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] in {"reading_comprehension", "listening_comprehension"}:
            if activity["type"] == "listening_comprehension":
                transcript = data.get("transcript")
                if isinstance(transcript, str):
                    data["transcript"] = _clean_listening_transcript(transcript)
            question = data.get("question", {})
            question.pop("correct_option_id", None)
            question["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] == "sentence_order":
            data.pop("correct_order", None)
            data["explanation"] = "Submit an answer to see the explanation."
    return result


_LISTENING_TRANSCRIPT_BOILERPLATE = {
    "please answer",
    "the group compares this detail before choosing an option",
    "each person checks the supplied information before agreeing",
    "they explain how the detail affects the practical next step",
    "finally the group records the decision for everyone to follow",
    "the complete plan now reflects the evidence in the message",
}


def _clean_listening_transcript(transcript: str) -> str:
    original_lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    had_legacy_boilerplate = any(
        _normalize_text_answer(line) in _LISTENING_TRANSCRIPT_BOILERPLATE
        for line in original_lines
    )
    lines = [
        line
        for line in original_lines
        if _normalize_text_answer(line) not in _LISTENING_TRANSCRIPT_BOILERPLATE
    ]
    if had_legacy_boilerplate and lines and lines[0].endswith("?"):
        lines.pop(0)
    lines = [
        re.sub(r"^speaker\s*:\s*", "", line, flags=re.IGNORECASE)
        for line in lines
    ]
    return "\n".join(lines) if lines else transcript


def _grade_activity(
    activity: dict,
    payload: ActivityAttemptInput,
    *,
    trusted_pronunciation: dict | None = None,
) -> tuple[bool | None, int, str, bool]:
    kind = activity["type"]
    data = activity["data"]
    if kind == "pronunciation_drill":
        if trusted_pronunciation is None:
            raise PlpInvalidAttemptError(
                "record and score an assigned target before completing this sound check"
            )
        target = str(trusted_pronunciation.get("target", ""))
        allowed = {
            _normalize_text_answer(_practice_item_text(item))
            for item in data.get("practice_items", [])
        }
        if _normalize_text_answer(target) not in allowed:
            raise PlpInvalidAttemptError(
                "the pronunciation target does not belong to this sound check"
            )
        accuracy = _bounded_pronunciation_metric(
            trusted_pronunciation.get("accuracy"), "accuracy"
        )
        completeness = _bounded_pronunciation_metric(
            trusted_pronunciation.get("completeness"), "completeness"
        )
        score = round((accuracy * 0.8) + (completeness * 0.2))
        passed = (
            accuracy >= PRONUNCIATION_PASS_ACCURACY
            and completeness >= PRONUNCIATION_PASS_COMPLETENESS
        )
        explanation = (
            f"Sound check passed with {accuracy}% accuracy and "
            f"{completeness}% completeness."
            if passed
            else (
                f"Try again: reach at least {PRONUNCIATION_PASS_ACCURACY}% "
                f"accuracy and {PRONUNCIATION_PASS_COMPLETENESS}% completeness."
            )
        )
        return passed, score, explanation, True
    if kind == "multiple_choice":
        valid_ids = {item["id"] for item in data["options"]}
        if payload.selected_option_id not in valid_ids:
            raise PlpInvalidAttemptError("choose one of the available options")
        correct = payload.selected_option_id == data["correct_option_id"]
        return correct, 100 if correct else 0, data["explanation"], True
    if kind == "fill_blank":
        answer = _normalize_text_answer(payload.text_answer or "")
        if not answer:
            raise PlpInvalidAttemptError("enter an answer before submitting")
        accepted = {_normalize_text_answer(item) for item in data["accepted_answers"]}
        correct = answer in accepted
        return correct, 100 if correct else 0, data["explanation"], True
    if kind in {"reading_comprehension", "listening_comprehension"}:
        question = data["question"]
        valid_ids = {item["id"] for item in question["options"]}
        if payload.selected_option_id not in valid_ids:
            raise PlpInvalidAttemptError("choose one of the available options")
        correct = payload.selected_option_id == question["correct_option_id"]
        return correct, 100 if correct else 0, question["explanation"], True
    if kind == "sentence_order":
        submitted = payload.ordered_token_ids or []
        valid_ids = {item["id"] for item in data["tokens"]}
        if len(submitted) != len(valid_ids) or set(submitted) != valid_ids:
            raise PlpInvalidAttemptError("use every sentence chunk exactly once")
        correct = payload.ordered_token_ids == data["correct_order"]
        return correct, 100 if correct else 0, data["explanation"], True
    if kind == "guided_speaking":
        transcript = (payload.transcript or "").casefold()
        covered = any(item.casefold() in transcript for item in data["target_expressions"])
        long_enough = (payload.duration_seconds or 0) >= data["minimum_seconds"]
        score = 100 if covered and long_enough else 50 if covered or long_enough else 0
        return None, score, "Participation is recorded; this is not an acoustic pronunciation grade.", False
    return None, 100, "Activity completed.", False


def _normalize_text_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("’", "'")
    normalized = " ".join(normalized.split())
    return normalized.strip(" \t\r\n.,!?;:")


def _correct_response(activity: dict) -> dict | None:
    kind = activity["type"]
    data = activity["data"]
    if kind == "multiple_choice":
        return {"selected_option_id": data["correct_option_id"]}
    if kind in {"reading_comprehension", "listening_comprehension"}:
        return {"selected_option_id": data["question"]["correct_option_id"]}
    if kind == "fill_blank":
        return {"text_answer": data["accepted_answers"][0]}
    if kind == "sentence_order":
        return {"ordered_token_ids": data["correct_order"]}
    return None


def _required_activities(lesson: PlanLesson) -> list[str]:
    return [
        item["id"] for item in (lesson.content or {}).get("content", {}).get("activities", [])
        if item.get("required", True)
    ]


def _scored_activities(lesson: PlanLesson) -> list[dict]:
    scored_types = {
        "pronunciation_drill",
        "multiple_choice",
        "fill_blank",
        "reading_comprehension",
        "listening_comprehension",
        "sentence_order",
    }
    return [
        item
        for item in (lesson.content or {}).get("content", {}).get("activities", [])
        if item.get("required", True) and item.get("type") in scored_types
    ]


def _practice_item_text(item: str | dict) -> str:
    return item if isinstance(item, str) else str(item.get("text", ""))


def _bounded_pronunciation_metric(value: object, name: str) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PlpInvalidAttemptError(f"pronunciation {name} is missing")
    rounded = round(float(value))
    if rounded < 0 or rounded > 100:
        raise PlpInvalidAttemptError(f"pronunciation {name} is invalid")
    return rounded


def _classify_failure(message: str) -> str:
    normalized = message.casefold()
    if "rate-limit" in normalized or "rate limit" in normalized:
        return "rate_limited"
    if "groq" in normalized or "ollama" in normalized or "scenario writer" in normalized:
        return "provider_validation"
    if "retriev" in normalized or "curriculum" in normalized:
        return "retrieval"
    if "validation" in normalized or "compiler" in normalized:
        return "content_validation"
    return "internal"


def _encode_job_failure(
    message: str,
    *,
    failure_kind: str,
    retry_after_seconds: int | None,
) -> str:
    payload = {
        "message": message[:1800],
        "failure_kind": failure_kind,
        "retry_after_seconds": retry_after_seconds,
    }
    return FAILURE_ENVELOPE_PREFIX + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode_job_failure(value: str | None) -> dict | None:
    if not value:
        return None
    if value.startswith(FAILURE_ENVELOPE_PREFIX):
        try:
            payload = json.loads(value[len(FAILURE_ENVELOPE_PREFIX):])
            if isinstance(payload, dict) and isinstance(payload.get("message"), str):
                return {
                    "message": payload["message"],
                    "failure_kind": str(
                        payload.get("failure_kind") or _classify_failure(payload["message"])
                    ),
                    "retry_after_seconds": payload.get("retry_after_seconds"),
                }
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {
        "message": value,
        "failure_kind": _classify_failure(value),
        "retry_after_seconds": None,
    }


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
    # Backward compatibility for already-stored v2 checkpoints that predate
    # explicit activity-to-skill binding. Curated checkpoints were assembled
    # round-robin from the lesson's ordered skill list.
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


def _current_streak(values: list[date]) -> int:
    dates = set(values)
    cursor = date.today()
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
        scenario_version=item.scenario_version,
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
        evaluation_version=item.evaluation_version,
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
