"""cover letters

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "cover_letters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("resume_version_id", sa.Uuid(), nullable=True),
        sa.Column("job_title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("length", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("notice", sa.String(500), nullable=True),
        sa.Column("paragraphs", postgresql.JSONB(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cover_letters"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_cover_letters_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="SET NULL", name="fk_cover_letters_job_id_jobs"
        ),
        sa.ForeignKeyConstraint(
            ["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL",
            name="fk_cover_letters_resume_version_id_resume_versions",
        ),
        sa.UniqueConstraint("user_id", "version", name="uq_cover_letters_user_version"),
        sa.CheckConstraint(
            "status IN ('generating', 'ready', 'failed', 'saved')", name="ck_cover_letters_status"
        ),
        sa.CheckConstraint("tone IN ('professional', 'warm', 'concise')", name="ck_cover_letters_tone"),
        sa.CheckConstraint("length IN ('short', 'medium')", name="ck_cover_letters_length"),
    )  # fmt: skip
    op.create_index("ix_cover_letters_user_id_job_id", "cover_letters", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_cover_letters_user_id_job_id", table_name="cover_letters")
    op.drop_table("cover_letters")
