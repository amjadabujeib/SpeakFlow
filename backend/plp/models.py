from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import EMBEDDING_DIMENSIONS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), default="local_guest")
    email: Mapped[str | None] = mapped_column(
        String(320), nullable=True, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('registered', 'guest', 'local_guest')",
            name="ck_users_kind",
        ),
        CheckConstraint(
            "(kind = 'registered' AND email IS NOT NULL "
            "AND password_hash IS NOT NULL) OR "
            "(kind IN ('guest', 'local_guest') AND email IS NULL "
            "AND password_hash IS NULL)",
            name="ck_users_auth_shape",
        ),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class RoleplaySession(Base):
    __tablename__ = "roleplay_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_session_id: Mapped[str] = mapped_column(String(80))
    scenario_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    scenario_version: Mapped[int] = mapped_column(Integer, default=1)
    cefr_level: Mapped[str] = mapped_column(String(2), default="B1")
    scenario: Mapped[str] = mapped_column(String(160), index=True)
    scenario_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    successful_turns: Mapped[int] = mapped_column(Integer, default=0)
    spoken_word_count: Mapped[int] = mapped_column(Integer, default=0)
    voiced_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    alignment_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_word_confidence: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    average_fluency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_prosody: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_words: Mapped[list] = mapped_column(JSONB, default=list)
    objective_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSONB, default=dict)
    evaluation_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "client_session_id",
            name="uq_roleplay_sessions_user_client_id",
        ),
        CheckConstraint("duration_seconds BETWEEN 0 AND 21600"),
        CheckConstraint("message_count BETWEEN 0 AND 500"),
        CheckConstraint("successful_turns BETWEEN 0 AND 500"),
        CheckConstraint("spoken_word_count BETWEEN 0 AND 50000"),
        CheckConstraint("voiced_seconds BETWEEN 0 AND 21600"),
        CheckConstraint(
            "alignment_coverage IS NULL OR alignment_coverage BETWEEN 0 AND 1"
        ),
        CheckConstraint(
            "average_word_confidence IS NULL OR "
            "average_word_confidence BETWEEN 0 AND 100"
        ),
        CheckConstraint(
            "average_fluency IS NULL OR average_fluency BETWEEN 0 AND 100"
        ),
        CheckConstraint(
            "average_prosody IS NULL OR average_prosody BETWEEN 0 AND 100"
        ),
    )


class RoleplayTurn(Base):
    __tablename__ = "roleplay_turns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roleplay_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    turn_id: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)
    input_mode: Mapped[str] = mapped_column(String(16))
    user_text: Mapped[str] = mapped_column(Text)
    assistant_text: Mapped[str] = mapped_column(Text)
    grammar_corrected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    grammar_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    grammar_error_units: Mapped[float] = mapped_column(Float, default=0.0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    word_feedback: Mapped[list] = mapped_column(JSONB, default=list)
    delivery_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    objective_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    __table_args__ = (
        UniqueConstraint("session_id", "turn_id"),
        UniqueConstraint("session_id", "sequence"),
        CheckConstraint("sequence BETWEEN 1 AND 500"),
        CheckConstraint("grammar_error_units >= 0"),
        CheckConstraint("word_count BETWEEN 0 AND 10000"),
    )


class RoleplayScenario(Base):
    __tablename__ = "roleplay_scenarios"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    definition: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    cefr_level: Mapped[str] = mapped_column(String(2))
    native_language: Mapped[str] = mapped_column(String(40))
    support_language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    learning_goals: Mapped[list] = mapped_column(JSONB)
    interests: Mapped[list] = mapped_column(JSONB)
    preferred_contexts: Mapped[list] = mapped_column(JSONB)
    accent_preference: Mapped[str] = mapped_column(String(24))
    days_per_week: Mapped[int] = mapped_column(Integer)
    minutes_per_day: Mapped[int] = mapped_column(Integer)
    pronunciation_priorities: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        CheckConstraint("days_per_week BETWEEN 2 AND 7"),
        CheckConstraint("minutes_per_day BETWEEN 10 AND 60"),
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    cefr_level: Mapped[str] = mapped_column(String(2), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    outcomes: Mapped[list] = mapped_column(JSONB)
    l1_tags: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SkillPrerequisite(Base):
    __tablename__ = "skill_prerequisites"

    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    prerequisite_skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        CheckConstraint("skill_id <> prerequisite_skill_id"),
    )


class CurriculumSource(Base):
    __tablename__ = "curriculum_sources"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    author: Mapped[str] = mapped_column(String(180), default="Project curriculum team")
    locator: Mapped[str] = mapped_column(String(500))
    license: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(80))
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class CurriculumChunk(Base):
    __tablename__ = "curriculum_chunks"

    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_sources.id", ondelete="RESTRICT"), index=True
    )
    object_type: Mapped[str] = mapped_column(String(40), index=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB)
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        Index("ix_curriculum_chunks_metadata", "metadata", postgresql_using="gin"),
        Index("ix_curriculum_chunks_search", "search_vector", postgresql_using="gin"),
    )


class CurriculumConcept(Base):
    """A source-attributed external curriculum claim, not a ready lesson."""

    __tablename__ = "curriculum_concepts"

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_sources.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(180))
    concept_type: Mapped[str] = mapped_column(String(32), index=True)
    cefr_level: Mapped[str | None] = mapped_column(String(2), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_tags: Mapped[list] = mapped_column(JSONB, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    review_status: Mapped[str] = mapped_column(String(24), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        Index("ix_curriculum_concepts_topics", "topic_tags", postgresql_using="gin"),
    )


class LearningPlan(Base):
    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    active_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "plan_revisions.id",
            name="fk_learning_plans_active_revision",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PlanRevision(Base):
    __tablename__ = "plan_revisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_plans.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), index=True)
    learner_snapshot: Mapped[dict] = mapped_column(JSONB)
    outline: Mapped[dict] = mapped_column(JSONB)
    planner_version: Mapped[str] = mapped_column(String(80))
    generator_version: Mapped[str] = mapped_column(String(80))
    generation_reason: Mapped[str] = mapped_column(String(80), default="onboarding")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (UniqueConstraint("plan_id", "revision"),)


class PlanLesson(Base):
    __tablename__ = "plan_lessons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_revisions.id", ondelete="CASCADE"), index=True
    )
    lesson_key: Mapped[str] = mapped_column(String(100))
    week_sequence: Mapped[int] = mapped_column(Integer)
    unit_sequence: Mapped[int] = mapped_column(Integer, default=1)
    lesson_sequence: Mapped[int] = mapped_column(Integer)
    lesson_type: Mapped[str] = mapped_column(String(32))
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    xp: Mapped[int] = mapped_column(Integer)
    skill_ids: Mapped[list] = mapped_column(JSONB)
    required_lesson_keys: Mapped[list] = mapped_column(JSONB)
    specification: Mapped[dict] = mapped_column(JSONB)
    content_status: Mapped[str] = mapped_column(String(20), index=True, default="pending")
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_refs: Mapped[list] = mapped_column(JSONB, default=list)
    generation_attempts: Mapped[int] = mapped_column(Integer, default=0)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("revision_id", "lesson_key"),
        UniqueConstraint(
            "revision_id", "week_sequence", "unit_sequence", "lesson_sequence"
        ),
    )


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_revisions.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(40), index=True, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_lessons.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    completed_activity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    best_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "best_score IS NULL OR best_score BETWEEN 0 AND 100",
            name="ck_lesson_progress_best_score",
        ),
        CheckConstraint("attempts >= 0", name="ck_lesson_progress_attempts"),
    )


class ActivityAttempt(Base):
    __tablename__ = "activity_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_lessons.id", ondelete="CASCADE"), index=True
    )
    activity_id: Mapped[str] = mapped_column(String(100))
    response: Mapped[dict] = mapped_column(JSONB)
    score: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 100",
            name="ck_activity_attempts_score",
        ),
    )


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"), index=True
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_attempts.id", ondelete="CASCADE")
    )
    score: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 100",
            name="ck_skill_evidence_score",
        ),
        CheckConstraint("weight > 0", name="ck_skill_evidence_weight"),
    )


class StudyDay(Base):
    __tablename__ = "study_days"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    studied_on: Mapped[date] = mapped_column(Date, primary_key=True, default=date.today)


class AdaptationProposal(Base):
    __tablename__ = "adaptation_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_plans.id", ondelete="CASCADE"), index=True
    )
    base_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_revisions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    summary: Mapped[str] = mapped_column(Text)
    changes: Mapped[list] = mapped_column(JSONB)
    evidence: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
