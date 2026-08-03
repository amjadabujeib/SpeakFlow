"""Standardize learning-plan and roleplay contracts."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_09"
down_revision: str | None = "20260801_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plan_revisions
        SET outline = replace(
            outline::text,
            '"mission_v3"',
            '"weekly_mission"'
        )::jsonb
        """
    )
    op.execute(
        """
        UPDATE plan_lessons
        SET specification = replace(
            specification::text,
            '"mission_v3"',
            '"weekly_mission"'
        )::jsonb
        """
    )
    op.execute(
        """
        UPDATE plan_lessons
        SET content = content - 'generator_version'
        WHERE jsonb_typeof(content) = 'object'
        """
    )
    op.execute(
        """
        UPDATE roleplay_scenarios
        SET definition = definition - 'version'
        WHERE jsonb_typeof(definition) = 'object'
        """
    )
    op.execute(
        """
        UPDATE roleplay_sessions
        SET scenario_snapshot = scenario_snapshot - 'version',
            evaluation = evaluation - 'evaluation_version'
        WHERE jsonb_typeof(scenario_snapshot) = 'object'
          AND jsonb_typeof(evaluation) = 'object'
        """
    )

    op.drop_column("plan_revisions", "planner_version")
    op.drop_column("plan_revisions", "generator_version")
    op.drop_column("roleplay_sessions", "scenario_version")
    op.drop_column("roleplay_sessions", "evaluation_version")
    op.drop_column("roleplay_scenarios", "version")


def downgrade() -> None:
    op.add_column(
        "plan_revisions",
        sa.Column(
            "generator_version",
            sa.String(80),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "plan_revisions",
        sa.Column(
            "planner_version",
            sa.String(80),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column(
            "scenario_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "roleplay_sessions",
        sa.Column("evaluation_version", sa.String(80), nullable=True),
    )
    op.add_column(
        "roleplay_scenarios",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.execute(
        """
        UPDATE plan_revisions
        SET outline = replace(
            outline::text,
            '"weekly_mission"',
            '"mission_v3"'
        )::jsonb
        """
    )
    op.execute(
        """
        UPDATE plan_lessons
        SET specification = replace(
            specification::text,
            '"weekly_mission"',
            '"mission_v3"'
        )::jsonb
        """
    )
