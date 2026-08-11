"""Persist whether a roleplay learner turn was semantically meaningful."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_12"
down_revision: str | None = "20260809_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roleplay_turns",
        sa.Column(
            "turn_status",
            sa.String(length=16),
            nullable=False,
            server_default="meaningful",
        ),
    )
    op.create_check_constraint(
        "ck_roleplay_turns_turn_status",
        "roleplay_turns",
        "turn_status IN ('meaningful', 'unclear', 'off_topic')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_roleplay_turns_turn_status",
        "roleplay_turns",
        type_="check",
    )
    op.drop_column("roleplay_turns", "turn_status")
