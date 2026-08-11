"""Add registered and guest authentication sessions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_07"
down_revision: str | None = "20260726_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(320)))
    op.add_column("users", sa.Column("display_name", sa.String(80)))
    op.add_column("users", sa.Column("password_hash", sa.Text()))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_check_constraint(
        "ck_users_kind",
        "users",
        "kind IN ('registered', 'guest', 'local_guest')",
    )
    op.create_check_constraint(
        "ck_users_auth_shape",
        "users",
        "(kind = 'registered' AND email IS NOT NULL "
        "AND password_hash IS NOT NULL) OR "
        "(kind IN ('guest', 'local_guest') AND email IS NULL "
        "AND password_hash IS NULL)",
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column(
            "cefr_level",
            sa.String(2),
            nullable=False,
            server_default="B1",
        ),
    )
    op.drop_constraint(
        "roleplay_sessions_client_session_id_key",
        "roleplay_sessions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_roleplay_sessions_user_client_id",
        "roleplay_sessions",
        ["user_id", "client_session_id"],
    )

    op.create_table(
        "auth_sessions",
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
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_id",
        "auth_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_auth_sessions_token_hash",
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_constraint(
        "uq_roleplay_sessions_user_client_id",
        "roleplay_sessions",
        type_="unique",
    )
    op.create_unique_constraint(
        "roleplay_sessions_client_session_id_key",
        "roleplay_sessions",
        ["client_session_id"],
    )
    op.drop_column("roleplay_sessions", "cefr_level")
    op.drop_constraint("ck_users_auth_shape", "users", type_="check")
    op.drop_constraint("ck_users_kind", "users", type_="check")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
