"""Persist roleplay session summaries."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260724_03"
down_revision: str | None = "20260721_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roleplay_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_session_id", sa.String(80), nullable=False, unique=True),
        sa.Column("scenario", sa.String(160), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("average_word_confidence", sa.Integer()),
        sa.Column("average_fluency", sa.Integer()),
        sa.Column("average_prosody", sa.Integer()),
        sa.Column("review_words", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_seconds BETWEEN 0 AND 21600"),
        sa.CheckConstraint("message_count BETWEEN 0 AND 500"),
        sa.CheckConstraint(
            "average_word_confidence IS NULL OR "
            "average_word_confidence BETWEEN 0 AND 100"
        ),
        sa.CheckConstraint(
            "average_fluency IS NULL OR average_fluency BETWEEN 0 AND 100"
        ),
        sa.CheckConstraint(
            "average_prosody IS NULL OR average_prosody BETWEEN 0 AND 100"
        ),
    )
    op.create_index(
        "ix_roleplay_sessions_user_id",
        "roleplay_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_roleplay_sessions_scenario",
        "roleplay_sessions",
        ["scenario"],
    )
    op.create_index(
        "ix_roleplay_sessions_created_at",
        "roleplay_sessions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("roleplay_sessions")
