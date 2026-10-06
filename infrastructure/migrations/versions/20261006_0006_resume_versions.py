"""resume versions: tailored resumes with proposed changes and approved content

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("job_title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("notice", sa.String(500), nullable=True),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_resume_versions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_resume_versions_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="SET NULL", name="fk_resume_versions_job_id_jobs"
        ),
        sa.UniqueConstraint("user_id", "version", name="uq_resume_versions_user_version"),
        sa.CheckConstraint(
            "status IN ('generating', 'ready', 'failed', 'saved')", name="ck_resume_versions_status"
        ),
    )
    op.create_index("ix_resume_versions_user_id_job_id", "resume_versions", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_resume_versions_user_id_job_id", table_name="resume_versions")
    op.drop_table("resume_versions")
