"""Learning-plan progress, attempt, and adaptation API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from .schema_core import (
    GenerationView,
    LearnerSnapshot,
    PlanView,
    SourceView,
    StrictModel,
)


class PronunciationActivityProgressView(StrictModel):
    verified_target_keys: list[str] = Field(default_factory=list)
    unverified_target_keys: list[str] = Field(default_factory=list)


class LessonProgressView(StrictModel):
    status: Literal["in_progress", "completed"]
    progress_fraction: float = Field(ge=0, le=1)
    best_score: int | None = Field(default=None, ge=0, le=100)
    attempts: int = Field(ge=0)
    completed_activity_ids: list[str] = Field(default_factory=list)
    pronunciation_activity_progress: dict[str, PronunciationActivityProgressView] = (
        Field(default_factory=dict)
    )
    completed_at: datetime | None = None


class ProgressView(StrictModel):
    current_lesson_id: str | None
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    weekly_goal_days: Literal[5] = 5
    studied_dates_this_week: list[str]
    lesson_states: dict[str, LessonProgressView]


class PlpDocument(StrictModel):
    format_revision: Literal[1] = 1
    generation: GenerationView
    plan: PlanView
    learner_snapshot: LearnerSnapshot
    progress: ProgressView
    knowledge_sources: list[SourceView]


class GenerationAccepted(StrictModel):
    job_id: UUID
    plan_id: UUID
    status: Literal["queued"] = "queued"


class GenerationCreateInput(StrictModel):
    """Select whether creation may replace an idle just-in-time roadmap."""

    regenerate: bool = False


class ActivityAttemptInput(StrictModel):
    attempt_kind: Literal["initial", "correction"] = "initial"
    submission_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_\-:.]{8,180}$",
    )
    attempt_session_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_\-]{8,80}$",
    )
    selected_option_id: str | None = Field(default=None, max_length=100)
    text_answer: str | None = Field(default=None, max_length=1000)
    ordered_token_ids: list[Annotated[str, Field(max_length=100)]] | None = Field(
        default=None,
        max_length=100,
    )
    transcript: str | None = Field(default=None, max_length=3000)
    duration_seconds: float | None = Field(default=None, ge=0, le=600)
    timezone_offset_minutes: int = Field(default=0, ge=-720, le=840)


class ActivityAttemptResult(StrictModel):
    correct: bool | None
    score: int = Field(ge=0, le=100)
    diagnostic_score: int | None = Field(default=None, ge=0, le=100)
    explanation: str
    correct_response: dict | None = None
    first_attempt: bool
    mastery_evidence_recorded: bool
    pronunciation_target_completed: bool = False
    pronunciation_mastery_verified: bool | None = None
    lesson_score: int | None = Field(default=None, ge=0, le=100)
    lesson_completed: bool
    newly_completed: bool = False
    xp_awarded: int = Field(default=0, ge=0)
    lesson_progress: LessonProgressView


class AdaptationProposalView(StrictModel):
    id: UUID
    status: Literal["pending", "approved", "rejected"]
    summary: str
    changes: list[dict]
    evidence: list[dict]
    created_at: datetime
