"""Make roleplay sessions server-authoritative and evidence based."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260726_06"
down_revision: str | None = "20260726_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roleplay_sessions", sa.Column("scenario_id", sa.String(100)))
    op.add_column(
        "roleplay_sessions",
        sa.Column("scenario_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column(
            "scenario_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column("status", sa.String(24), nullable=False, server_default="complete"),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column("successful_turns", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column("spoken_word_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column("voiced_seconds", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("roleplay_sessions", sa.Column("alignment_coverage", sa.Float()))
    op.add_column(
        "roleplay_sessions",
        sa.Column(
            "objective_state",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column(
            "evaluation",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("roleplay_sessions", sa.Column("evaluation_version", sa.String(80)))
    op.add_column("roleplay_sessions", sa.Column("ended_reason", sa.String(32)))
    op.add_column("roleplay_sessions", sa.Column("ended_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_roleplay_sessions_scenario_id", "roleplay_sessions", ["scenario_id"]
    )
    op.create_index("ix_roleplay_sessions_status", "roleplay_sessions", ["status"])
    op.create_check_constraint(
        "ck_roleplay_successful_turns",
        "roleplay_sessions",
        "successful_turns BETWEEN 0 AND 500",
    )
    op.create_check_constraint(
        "ck_roleplay_spoken_word_count",
        "roleplay_sessions",
        "spoken_word_count BETWEEN 0 AND 50000",
    )
    op.create_check_constraint(
        "ck_roleplay_voiced_seconds",
        "roleplay_sessions",
        "voiced_seconds BETWEEN 0 AND 21600",
    )
    op.create_check_constraint(
        "ck_roleplay_alignment_coverage",
        "roleplay_sessions",
        "alignment_coverage IS NULL OR alignment_coverage BETWEEN 0 AND 1",
    )

    op.create_table(
        "roleplay_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roleplay_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_id", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("input_mode", sa.String(16), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("assistant_text", sa.Text(), nullable=False),
        sa.Column("grammar_corrected_text", sa.Text()),
        sa.Column("grammar_feedback", sa.Text()),
        sa.Column(
            "grammar_error_units", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "word_feedback",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "delivery_metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "objective_evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "turn_id"),
        sa.UniqueConstraint("session_id", "sequence"),
        sa.CheckConstraint("sequence BETWEEN 1 AND 500"),
        sa.CheckConstraint("grammar_error_units >= 0"),
        sa.CheckConstraint("word_count BETWEEN 0 AND 10000"),
    )
    op.create_index("ix_roleplay_turns_session_id", "roleplay_turns", ["session_id"])
    op.create_index("ix_roleplay_turns_created_at", "roleplay_turns", ["created_at"])

    op.create_table(
        "roleplay_scenarios",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_roleplay_scenarios_user_id", "roleplay_scenarios", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("roleplay_scenarios")
    op.drop_table("roleplay_turns")
    op.drop_constraint(
        "ck_roleplay_alignment_coverage", "roleplay_sessions", type_="check"
    )
    op.drop_constraint(
        "ck_roleplay_voiced_seconds", "roleplay_sessions", type_="check"
    )
    op.drop_constraint(
        "ck_roleplay_spoken_word_count", "roleplay_sessions", type_="check"
    )
    op.drop_constraint(
        "ck_roleplay_successful_turns", "roleplay_sessions", type_="check"
    )
    op.drop_index("ix_roleplay_sessions_status", table_name="roleplay_sessions")
    op.drop_index(
        "ix_roleplay_sessions_scenario_id", table_name="roleplay_sessions"
    )
    for name in (
        "ended_at",
        "ended_reason",
        "evaluation_version",
        "evaluation",
        "objective_state",
        "alignment_coverage",
        "voiced_seconds",
        "spoken_word_count",
        "successful_turns",
        "status",
        "scenario_snapshot",
        "scenario_version",
        "scenario_id",
    ):
        op.drop_column("roleplay_sessions", name)
