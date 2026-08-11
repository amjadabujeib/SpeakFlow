"""Add administrator authorization and privileged-action auditing."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_10"
down_revision: str | None = "20260802_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "admin_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_events_actor_user_id",
        "admin_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_admin_audit_events_target_user_id",
        "admin_audit_events",
        ["target_user_id"],
    )
    op.create_index(
        "ix_admin_audit_events_action",
        "admin_audit_events",
        ["action"],
    )
    op.create_index(
        "ix_admin_audit_events_created_at",
        "admin_audit_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_audit_events_created_at",
        table_name="admin_audit_events",
    )
    op.drop_index(
        "ix_admin_audit_events_action",
        table_name="admin_audit_events",
    )
    op.drop_index(
        "ix_admin_audit_events_target_user_id",
        table_name="admin_audit_events",
    )
    op.drop_index(
        "ix_admin_audit_events_actor_user_id",
        table_name="admin_audit_events",
    )
    op.drop_table("admin_audit_events")
    op.drop_column("users", "is_admin")
