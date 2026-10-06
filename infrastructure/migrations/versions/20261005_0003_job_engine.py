"""job engine: jobs, search_runs, job_source_configs

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def _array(length: int) -> postgresql.ARRAY:  # type: ignore[type-arg]
    return postgresql.ARRAY(sa.String(length))


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], ondelete="CASCADE", name=f"fk_{table}_user_id_users"
    )


def upgrade() -> None:
    empty = sa.text("'{}'")
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_job_id", sa.String(200), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("locations", _array(200), server_default=empty, nullable=False),
        sa.Column("cities", _array(100), server_default=empty, nullable=False),
        sa.Column("countries", _array(100), server_default=empty, nullable=False),
        sa.Column("remote_type", sa.String(16), nullable=False),
        sa.Column("remote_regions", _array(100), server_default=empty, nullable=False),
        sa.Column("employment_type", sa.String(16), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(3), nullable=True),
        sa.Column("salary_period", sa.String(8), nullable=True),
        sa.Column("salary_text", sa.String(300), nullable=True),
        sa.Column("salary_unknown", sa.Boolean(), nullable=False),
        sa.Column("experience_min_years", sa.Integer(), nullable=True),
        sa.Column("experience_max_years", sa.Integer(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column(
            "also_seen_on", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("raw", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
        _user_fk("jobs"),
        sa.UniqueConstraint("user_id", "source", "source_job_id", name="uq_jobs_user_source_job"),
        sa.CheckConstraint(
            "remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')", name="ck_jobs_remote_type"
        ),
        sa.CheckConstraint(
            "employment_type IN ('full_time', 'contract', 'internship', 'part_time', 'unknown')",
            name="ck_jobs_employment_type",
        ),
        sa.CheckConstraint(
            "salary_period IN ('year', 'month', 'hour')", name="ck_jobs_salary_period"
        ),
    )
    op.create_index("ix_jobs_user_id_dedupe_key", "jobs", ["user_id", "dedupe_key"])
    op.create_index("ix_jobs_user_id_content_hash", "jobs", ["user_id", "content_hash"])
    op.create_index("ix_jobs_user_id_posted_at", "jobs", ["user_id", "posted_at"])

    op.create_table(
        "search_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("keywords", _array(100), server_default=empty, nullable=False),
        sa.Column(
            "source_results", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_search_runs"),
        _user_fk("search_runs"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')", name="ck_search_runs_status"
        ),
    )
    op.create_index("ix_search_runs_user_id_created_at", "search_runs", ["user_id", "created_at"])

    op.create_table(
        "job_source_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("identifier", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_source_configs"),
        _user_fk("job_source_configs"),
        sa.UniqueConstraint("user_id", "source", "identifier", name="uq_job_source_configs_key"),
    )


def downgrade() -> None:
    op.drop_table("job_source_configs")
    op.drop_index("ix_search_runs_user_id_created_at", table_name="search_runs")
    op.drop_table("search_runs")
    for name in ("posted_at", "content_hash", "dedupe_key"):
        op.drop_index(f"ix_jobs_user_id_{name}", table_name="jobs")
    op.drop_table("jobs")
