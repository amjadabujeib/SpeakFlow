"""Track whether grammar evaluation actually ran for each roleplay turn."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_11"
down_revision: str | None = "20260808_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roleplay_turns",
        sa.Column(
            "grammar_evaluated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("roleplay_turns", "grammar_evaluated")
