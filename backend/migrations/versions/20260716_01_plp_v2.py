"""Create the PLP v2 PostgreSQL schema."""

from typing import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260716_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normal PostgreSQL installs create pgvector here. The documented
    # user-owned /home installation may pre-load the packaged extension SQL
    # because PostgreSQL's compiled system extension directory is root-owned.
    op.execute(
        "DO $$ BEGIN IF to_regtype('vector') IS NULL THEN "
        "CREATE EXTENSION vector; END IF; END $$"
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "learner_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("native_language", sa.String(40), nullable=False),
        sa.Column("support_language", sa.String(40)),
        sa.Column("learning_goals", postgresql.JSONB(), nullable=False),
        sa.Column("interests", postgresql.JSONB(), nullable=False),
        sa.Column("preferred_contexts", postgresql.JSONB(), nullable=False),
        sa.Column("accent_preference", sa.String(24), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer(), nullable=False),
        sa.Column("pronunciation_priorities", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("days_per_week BETWEEN 2 AND 7"),
        sa.CheckConstraint("minutes_per_day BETWEEN 10 AND 60"),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("outcomes", postgresql.JSONB(), nullable=False),
        sa.Column("l1_tags", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_skills_domain", "skills", ["domain"])
    op.create_index("ix_skills_cefr_level", "skills", ["cefr_level"])
    op.create_table(
        "skill_prerequisites",
        sa.Column("skill_id", sa.String(120), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("prerequisite_skill_id", sa.String(120), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.CheckConstraint("skill_id <> prerequisite_skill_id"),
    )
    op.create_table(
        "curriculum_sources",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("author", sa.String(180), nullable=False),
        sa.Column("locator", sa.String(500), nullable=False),
        sa.Column("license", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "curriculum_chunks",
        sa.Column("id", sa.String(140), primary_key=True),
        sa.Column("source_id", sa.String(100), sa.ForeignKey("curriculum_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_curriculum_chunks_source_id", "curriculum_chunks", ["source_id"])
    op.create_index("ix_curriculum_chunks_object_type", "curriculum_chunks", ["object_type"])
    op.create_index("ix_curriculum_chunks_review_status", "curriculum_chunks", ["review_status"])
    op.create_index("ix_curriculum_chunks_metadata", "curriculum_chunks", ["metadata"], postgresql_using="gin")
    op.create_index("ix_curriculum_chunks_search", "curriculum_chunks", ["search_vector"], postgresql_using="gin")
    op.execute(
        "CREATE OR REPLACE FUNCTION plp_chunk_search_vector() RETURNS trigger AS $$ "
        "BEGIN NEW.search_vector := to_tsvector('english', coalesce(NEW.content, '')); RETURN NEW; END "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER curriculum_chunks_search_vector BEFORE INSERT OR UPDATE OF content "
        "ON curriculum_chunks FOR EACH ROW EXECUTE FUNCTION plp_chunk_search_vector()"
    )
    op.create_table(
        "learning_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learning_plans_user_id", "learning_plans", ["user_id"])
    op.create_table(
        "plan_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("learner_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("outline", postgresql.JSONB(), nullable=False),
        sa.Column("planner_version", sa.String(80), nullable=False),
        sa.Column("generator_version", sa.String(80), nullable=False),
        sa.Column("generation_reason", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "revision"),
    )
    op.create_index("ix_plan_revisions_plan_id", "plan_revisions", ["plan_id"])
    op.create_index("ix_plan_revisions_status", "plan_revisions", ["status"])
    op.create_table(
        "plan_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_key", sa.String(100), nullable=False),
        sa.Column("week_sequence", sa.Integer(), nullable=False),
        sa.Column("unit_sequence", sa.Integer(), nullable=False),
        sa.Column("lesson_sequence", sa.Integer(), nullable=False),
        sa.Column("lesson_type", sa.String(32), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("skill_ids", postgresql.JSONB(), nullable=False),
        sa.Column("required_lesson_keys", postgresql.JSONB(), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("content_status", sa.String(20), nullable=False),
        sa.Column("content", postgresql.JSONB()),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False),
        sa.Column("generation_attempts", sa.Integer(), nullable=False),
        sa.Column("generation_error", sa.Text()),
        sa.UniqueConstraint("revision_id", "lesson_key"),
        sa.UniqueConstraint("revision_id", "week_sequence", "unit_sequence", "lesson_sequence"),
    )
    op.create_index("ix_plan_lessons_revision_id", "plan_lessons", ["revision_id"])
    op.create_index("ix_plan_lessons_content_status", "plan_lessons", ["content_status"])
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_revisions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_table(
        "lesson_progress",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_lessons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_activity_ids", postgresql.JSONB(), nullable=False),
        sa.Column("best_score", sa.Integer()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "activity_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(100), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activity_attempts_user_id", "activity_attempts", ["user_id"])
    op.create_index("ix_activity_attempts_lesson_id", "activity_attempts", ["lesson_id"])
    op.create_table(
        "skill_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.String(120), sa.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activity_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skill_evidence_user_id", "skill_evidence", ["user_id"])
    op.create_index("ix_skill_evidence_skill_id", "skill_evidence", ["skill_id"])
    op.create_table(
        "study_days",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("studied_on", sa.Date(), primary_key=True),
    )
    op.create_table(
        "adaptation_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_adaptation_proposals_plan_id", "adaptation_proposals", ["plan_id"])


def downgrade() -> None:
    for table in (
        "adaptation_proposals", "study_days", "skill_evidence",
        "activity_attempts", "lesson_progress", "generation_jobs",
        "plan_lessons", "plan_revisions", "learning_plans",
        "curriculum_chunks", "curriculum_sources", "skill_prerequisites",
        "skills", "learner_profiles", "users",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS plp_chunk_search_vector()")
