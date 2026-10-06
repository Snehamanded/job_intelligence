import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class CoverLetter(UUIDPrimaryKey, Timestamps, Base):
    """A cover letter for one job: checked sentences, user decisions, then saved content."""

    __tablename__ = "cover_letters"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_cover_letters_user_version"),
        CheckConstraint("status IN ('generating', 'ready', 'failed', 'saved')", name="status"),
        CheckConstraint("tone IN ('professional', 'warm', 'concise')", name="tone"),
        CheckConstraint("length IN ('short', 'medium')", name="length"),
        Index("ix_cover_letters_user_id_job_id", "user_id", "job_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL")
    )
    job_title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tone: Mapped[str] = mapped_column(String(16), nullable=False)
    length: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # ai | template
    notice: Mapped[str | None] = mapped_column(String(500))
    # [{"id", "sentences": [{id, text, kind, sources, job_quote, source, status, issues,
    #                       included}]}]
    paragraphs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
