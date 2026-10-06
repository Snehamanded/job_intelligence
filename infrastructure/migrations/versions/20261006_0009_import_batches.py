"""import_batches: job posts pasted from email alerts or WhatsApp, imported in the background

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16)),
        # The pasted text, kept only until it has been processed.
        sa.Column("pasted_text", sa.Text()),
        sa.Column(
            "results", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("notice", sa.String(500)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_batches"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_import_batches_user_id_users"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_import_batches_status",
        ),
        sa.CheckConstraint(
            "channel IN ('email', 'whatsapp', 'other')", name="ck_import_batches_channel"
        ),
    )
    op.create_index(
        "ix_import_batches_user_id_created_at", "import_batches", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_import_batches_user_id_created_at", table_name="import_batches")
    op.drop_table("import_batches")
