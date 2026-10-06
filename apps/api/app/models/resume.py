import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey

RESUME_STATUSES = ("queued", "parsing", "parsed", "failed")
FILE_TYPES = ("pdf", "docx", "txt")


class Resume(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint(f"status IN {RESUME_STATUSES}", name="status"),
        CheckConstraint(f"file_type IN {FILE_TYPES}", name="file_type"),
        Index("ix_resumes_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Display only. Files are stored under server-generated names.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    error_message: Mapped[str | None] = mapped_column(String(500))
    parse_notice: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    text_sha256: Mapped[str | None] = mapped_column(String(64))
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
