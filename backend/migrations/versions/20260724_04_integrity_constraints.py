"""Strengthen learner-state relational and score integrity."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260724_04"
down_revision: str | None = "20260724_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_learning_plans_active_revision",
        "learning_plans",
        "plan_revisions",
        ["active_revision_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_check_constraint(
        "ck_lesson_progress_best_score",
        "lesson_progress",
        "best_score IS NULL OR best_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_lesson_progress_attempts",
        "lesson_progress",
        "attempts >= 0",
    )
    op.create_check_constraint(
        "ck_activity_attempts_score",
        "activity_attempts",
        "score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_skill_evidence_score",
        "skill_evidence",
        "score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_skill_evidence_weight",
        "skill_evidence",
        "weight > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_skill_evidence_weight",
        "skill_evidence",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_evidence_score",
        "skill_evidence",
        type_="check",
    )
    op.drop_constraint(
        "ck_activity_attempts_score",
        "activity_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_lesson_progress_attempts",
        "lesson_progress",
        type_="check",
    )
    op.drop_constraint(
        "ck_lesson_progress_best_score",
        "lesson_progress",
        type_="check",
    )
    op.drop_constraint(
        "fk_learning_plans_active_revision",
        "learning_plans",
        type_="foreignkey",
    )
