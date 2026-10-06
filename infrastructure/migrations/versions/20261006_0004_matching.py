"""matching: embeddings (pgvector), scoring_configs, job_matches, jobs.priority

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], ondelete="CASCADE", name=f"fk_{table}_user_id_users"
    )


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("priority", sa.Integer(), server_default=sa.text("1"), nullable=False)
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("vector", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_embeddings"),
        _user_fk("embeddings"),
        sa.UniqueConstraint("user_id", "content_hash", "model", name="uq_embeddings_key"),
    )

    op.create_table(
        "scoring_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_scoring_configs"),
        _user_fk("scoring_configs"),
        sa.UniqueConstraint("user_id", "version", name="uq_scoring_configs_user_version"),
    )

    op.create_table(
        "job_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("scoring_config_version", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("rank_score", sa.Float(), nullable=False),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("high_priority", sa.Boolean(), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("explanation_source", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_matches"),
        _user_fk("job_matches"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="CASCADE", name="fk_job_matches_job_id_jobs"
        ),
        sa.UniqueConstraint(
            "user_id", "job_id", "profile_version", "scoring_config_version",
            name="uq_job_matches_key",
        ),
    )  # fmt: skip
    op.create_index(
        "ix_job_matches_current",
        "job_matches",
        ["user_id", "profile_version", "scoring_config_version", "rank_score"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_matches_current", table_name="job_matches")
    op.drop_table("job_matches")
    op.drop_table("scoring_configs")
    op.drop_table("embeddings")
    op.drop_column("jobs", "priority")
