from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from speakflow.shared.orm import Base, utc_now


class RoleplaySession(Base):
    __tablename__ = "roleplay_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_session_id: Mapped[str] = mapped_column(String(80))
    scenario_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
