"""resume intelligence: resumes, profile data and preferences, llm usage, ai extraction cache

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(8), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("parse_notice", sa.String(500), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("text_sha256", sa.String(64), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_resumes"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_resumes_user_id_users"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'parsing', 'parsed', 'failed')", name="ck_resumes_status"
        ),
        sa.CheckConstraint("file_type IN ('pdf', 'docx', 'txt')", name="ck_resumes_file_type"),
    )
    op.create_index("ix_resumes_user_id_created_at", "resumes", ["user_id", "created_at"])

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_llm_usage"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_llm_usage_user_id_users"
        ),
    )
    op.create_index("ix_llm_usage_user_id_created_at", "llm_usage", ["user_id", "created_at"])

    op.create_table(
        "ai_extractions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_extractions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_ai_extractions_user_id_users"
        ),
        sa.UniqueConstraint(
            "user_id", "task", "content_hash", "prompt_version", "model",
            name="uq_ai_extractions_key",
        ),
    )

    with op.batch_alter_table("candidate_profiles") as t:
        t.add_column(sa.Column("resume_id", sa.Uuid(), nullable=True))
        t.add_column(sa.Column("origin", sa.String(16), server_default="parsed", nullable=False))
        t.add_column(sa.Column("parse_method", sa.String(16), nullable=True))
        t.add_column(
            sa.Column(
                "data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
            )
        )
        t.add_column(sa.Column("experience_months", sa.Integer(), nullable=True))
        t.add_column(
            sa.Column(
                "target_roles",
                postgresql.ARRAY(sa.String(100)),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        t.add_column(
            sa.Column("remote_scope", sa.String(16), server_default="none", nullable=False)
        )
        t.add_column(
            sa.Column(
                "onsite_locations",
                postgresql.ARRAY(sa.String(100)),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        t.add_column(
            sa.Column(
                "open_to",
                postgresql.ARRAY(sa.String(16)),
                server_default=sa.text("'{full_time}'"),
                nullable=False,
            )
        )
        t.add_column(sa.Column("min_salary", sa.Integer(), nullable=True))
        t.add_column(sa.Column("currency", sa.String(3), nullable=True))
        t.add_column(
            sa.Column(
                "salary_unknown_policy", sa.String(16), server_default="include", nullable=False
            )
        )
        t.create_foreign_key(
            "fk_candidate_profiles_resume_id_resumes",
            "resumes",
            ["resume_id"],
            ["id"],
            ondelete="SET NULL",
        )
        t.create_check_constraint("ck_candidate_profiles_origin", "origin IN ('parsed', 'edited')")
        t.create_check_constraint(
            "ck_candidate_profiles_parse_method", "parse_method IN ('llm', 'heuristic')"
        )
        t.create_check_constraint(
            "ck_candidate_profiles_remote_scope", "remote_scope IN ('none', 'india', 'worldwide')"
        )
        t.create_check_constraint(
            "ck_candidate_profiles_salary_unknown_policy",
            "salary_unknown_policy IN ('include', 'exclude')",
        )


def downgrade() -> None:
    with op.batch_alter_table("candidate_profiles") as t:
        for name in ("origin", "parse_method", "remote_scope", "salary_unknown_policy"):
            t.drop_constraint(f"ck_candidate_profiles_{name}", type_="check")
        t.drop_constraint("fk_candidate_profiles_resume_id_resumes", type_="foreignkey")
        for column in (
            "salary_unknown_policy",
            "currency",
            "min_salary",
            "open_to",
            "onsite_locations",
            "remote_scope",
            "target_roles",
            "experience_months",
            "data",
            "parse_method",
            "origin",
            "resume_id",
        ):
            t.drop_column(column)
    op.drop_table("ai_extractions")
    op.drop_index("ix_llm_usage_user_id_created_at", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_index("ix_resumes_user_id_created_at", table_name="resumes")
    op.drop_table("resumes")
