import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class Job(UUIDPrimaryKey, Timestamps, Base):
    """A normalized job posting. Text fields come from third parties and are untrusted."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "source_job_id", name="uq_jobs_user_source_job"),
        Index("ix_jobs_user_id_dedupe_key", "user_id", "dedupe_key"),
        Index("ix_jobs_user_id_content_hash", "user_id", "content_hash"),
        Index("ix_jobs_user_id_posted_at", "user_id", "posted_at"),
        CheckConstraint(
            "remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')", name="remote_type"
        ),
        CheckConstraint(
            "employment_type IN ('full_time', 'contract', 'internship', 'part_time', 'unknown')",
            name="employment_type",
        ),
        CheckConstraint("salary_period IN ('year', 'month', 'hour')", name="salary_period"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)

    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), server_default=text("'{}'"), nullable=False
    )
    cities: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    remote_type: Mapped[str] = mapped_column(String(16), nullable=False)
    remote_regions: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    employment_type: Mapped[str] = mapped_column(String(16), nullable=False)

    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(8))
    salary_text: Mapped[str | None] = mapped_column(String(300))
    # True when no salary could be read. A salary is never guessed.
    salary_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)

    experience_min_years: Mapped[int | None] = mapped_column(Integer)
    experience_max_years: Mapped[int | None] = mapped_column(Integer)

    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Other sources the same job was found on: [{"source", "source_job_id", "url"}].
    also_seen_on: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    raw: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    is_mock: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    # The user's own priority for ranking: 0 low, 1 normal, 2 high.
    priority: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SearchRun(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "search_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="status"),
        Index("ix_search_runs_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    # One entry per connector: status, fetched, kept, new, updated, duplicates, error, duration_ms.
    source_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobSourceConfig(UUIDPrimaryKey, Base):
    """A source the user wants searched, e.g. a Greenhouse board token."""

    __tablename__ = "job_source_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "identifier", name="uq_job_source_configs_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
