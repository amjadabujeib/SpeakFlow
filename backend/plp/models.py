from __future__ import annotations

import uuid
from datetime import date, datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from .config import EMBEDDING_DIMENSIONS
from speakflow.features.auth.infrastructure.models import AuthSession, User
from speakflow.features.roleplay.infrastructure.models import (
    RoleplayScenario,
    RoleplaySession,
    RoleplayTurn,
)
from speakflow.shared.orm import Base, utc_now


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
