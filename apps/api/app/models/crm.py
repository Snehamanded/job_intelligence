import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey

STAGES = ("saved", "applied", "interviewing", "offer", "rejected", "withdrawn")
INTERVIEW_KINDS = (
    "phone_screen", "technical", "system_design", "behavioral", "hiring_manager", "onsite", "other"
)  # fmt: skip
INTERVIEW_OUTCOMES = ("pending", "passed", "failed", "cancelled")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Application(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(_in("stage", STAGES), name="stage"),
        # One application per job; applications for jobs not in the app have no job_id.
        Index(
            "uq_applications_user_job", "user_id", "job_id", unique=True,
            postgresql_where=text("job_id IS NOT NULL"),
        ),
        Index("ix_applications_user_id_stage", "user_id", "stage"),
    )  # fmt: skip

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    # Snapshot, so the application keeps its meaning if the job is removed.
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    match_score: Mapped[int | None] = mapped_column(Integer)
    match_label: Mapped[str | None] = mapped_column(String(16))

    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    applied_at: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_action: Mapped[str | None] = mapped_column(String(300))
    next_action_date: Mapped[date | None] = mapped_column(Date)


class ApplicationEvent(UUIDPrimaryKey, Base):
    __tablename__ = "application_events"
    __table_args__ = (Index("ix_application_events_application_id", "application_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(16))
    to_stage: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApplicationNote(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "application_notes"
    __table_args__ = (Index("ix_application_notes_application_id", "application_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Interview(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(_in("kind", INTERVIEW_KINDS), name="kind"),
        CheckConstraint(_in("outcome", INTERVIEW_OUTCOMES), name="outcome"),
        Index("ix_interviews_user_id_scheduled_at", "user_id", "scheduled_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    outcome: Mapped[str] = mapped_column(String(16), server_default="pending", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # [{"text": str, "done": bool}]
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
