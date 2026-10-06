"""job crm: applications, application_events, application_notes, interviews

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()
STAGES = "'saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn'"
KINDS = "'phone_screen', 'technical', 'system_design', 'behavioral', 'hiring_manager', 'onsite', 'other'"
OUTCOMES = "'pending', 'passed', 'failed', 'cancelled'"


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], ondelete="CASCADE", name=f"fk_{table}_user_id_users"
    )


def _app_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["application_id"], ["applications.id"], ondelete="CASCADE",
        name=f"fk_{table}_application_id_applications",
    )  # fmt: skip


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_label", sa.String(16), nullable=True),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("applied_at", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action", sa.String(300), nullable=True),
        sa.Column("next_action_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
        _user_fk("applications"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="SET NULL", name="fk_applications_job_id_jobs"
        ),
        sa.CheckConstraint(f"stage IN ({STAGES})", name="ck_applications_stage"),
    )
    op.create_index(
        "uq_applications_user_job", "applications", ["user_id", "job_id"], unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )  # fmt: skip
    op.create_index("ix_applications_user_id_stage", "applications", ["user_id", "stage"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("from_stage", sa.String(16), nullable=True),
        sa.Column("to_stage", sa.String(16), nullable=True),
        sa.Column("detail", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_events"),
        _user_fk("application_events"),
        _app_fk("application_events"),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )

    op.create_table(
        "application_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_application_notes"),
        _user_fk("application_notes"),
        _app_fk("application_notes"),
    )
    op.create_index(
        "ix_application_notes_application_id", "application_notes", ["application_id"]
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("outcome", sa.String(16), server_default="pending", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "checklist", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_interviews"),
        _user_fk("interviews"),
        _app_fk("interviews"),
        sa.CheckConstraint(f"kind IN ({KINDS})", name="ck_interviews_kind"),
        sa.CheckConstraint(f"outcome IN ({OUTCOMES})", name="ck_interviews_outcome"),
    )
    op.create_index("ix_interviews_user_id_scheduled_at", "interviews", ["user_id", "scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_interviews_user_id_scheduled_at", table_name="interviews")
    op.drop_table("interviews")
    op.drop_index("ix_application_notes_application_id", table_name="application_notes")
    op.drop_table("application_notes")
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_applications_user_id_stage", table_name="applications")
    op.drop_index("uq_applications_user_job", table_name="applications")
    op.drop_table("applications")
