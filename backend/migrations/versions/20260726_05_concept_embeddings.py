"""Add semantic retrieval evidence to curriculum concepts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260726_05"
down_revision: str | None = "20260724_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "curriculum_concepts",
        sa.Column("embedding_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "curriculum_concepts",
        sa.Column("embedding", Vector(768), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("curriculum_concepts", "embedding")
    op.drop_column("curriculum_concepts", "embedding_model")
