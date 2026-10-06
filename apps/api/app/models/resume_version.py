import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class ResumeVersion(UUIDPrimaryKey, Timestamps, Base):
    """A resume tailored for one job. Changes are proposed, approved one by one, then saved."""

    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_resume_versions_user_version"),
        CheckConstraint("status IN ('generating', 'ready', 'failed', 'saved')", name="status"),
        Index("ix_resume_versions_user_id_job_id", "user_id", "job_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    # Snapshot so the version keeps its meaning if the job is removed.
    job_title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # ai | rules
    notice: Mapped[str | None] = mapped_column(String(500))
    # Proposed changes with labels, checks and the user's decisions.
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # The approved document, set on save and never changed afterwards.
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
