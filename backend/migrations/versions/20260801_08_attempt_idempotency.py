"""Serialize learner plans and make activity submissions idempotent."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_08"
down_revision: str | None = "20260726_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learner_profiles",
        sa.Column(
            "timezone_offset_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_learner_profiles_timezone_offset",
        "learner_profiles",
        "timezone_offset_minutes BETWEEN -720 AND 840",
    )
    op.create_unique_constraint(
        "uq_learning_plans_user_id",
        "learning_plans",
        ["user_id"],
    )
    op.add_column(
        "activity_attempts",
        sa.Column("submission_id", sa.String(length=180), nullable=True),
    )
    op.create_unique_constraint(
        "uq_activity_attempts_user_submission",
        "activity_attempts",
        ["user_id", "submission_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_activity_attempts_user_submission",
        "activity_attempts",
        type_="unique",
    )
    op.drop_column("activity_attempts", "submission_id")
    op.drop_constraint(
        "uq_learning_plans_user_id",
        "learning_plans",
        type_="unique",
    )
    op.drop_constraint(
        "ck_learner_profiles_timezone_offset",
        "learner_profiles",
        type_="check",
    )
    op.drop_column("learner_profiles", "timezone_offset_minutes")
