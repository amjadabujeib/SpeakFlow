"""Add source-attributed external curriculum concepts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_02"
down_revision: str | None = "20260716_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_concepts",
        sa.Column("id", sa.String(180), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(100),
            sa.ForeignKey("curriculum_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(180), nullable=False),
        sa.Column("concept_type", sa.String(32), nullable=False),
        sa.Column("cefr_level", sa.String(2)),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("topic_tags", postgresql.JSONB(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_id"),
    )
    op.create_index(
        "ix_curriculum_concepts_source_id", "curriculum_concepts", ["source_id"]
    )
    op.create_index(
        "ix_curriculum_concepts_concept_type",
        "curriculum_concepts",
        ["concept_type"],
    )
    op.create_index(
        "ix_curriculum_concepts_cefr_level",
        "curriculum_concepts",
        ["cefr_level"],
    )
    op.create_index(
        "ix_curriculum_concepts_review_status",
        "curriculum_concepts",
        ["review_status"],
    )
    op.create_index(
        "ix_curriculum_concepts_topics",
        "curriculum_concepts",
        ["topic_tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("curriculum_concepts")
