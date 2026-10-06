import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class CandidateProfile(UUIDPrimaryKey, Timestamps, Base):
    """One immutable version of the user's profile. Every change creates a new version."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_candidate_profiles_user_version"),
        CheckConstraint("origin IN ('parsed', 'edited')", name="origin"),
        CheckConstraint("parse_method IN ('llm', 'heuristic')", name="parse_method"),
        CheckConstraint("remote_scope IN ('none', 'india', 'worldwide')", name="remote_scope"),
        CheckConstraint(
            "salary_unknown_policy IN ('include', 'exclude')", name="salary_unknown_policy"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)

    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL")
    )
    origin: Mapped[str] = mapped_column(String(16), server_default="parsed", nullable=False)
    parse_method: Mapped[str | None] = mapped_column(String(16))
    # Structured profile (app.schemas.profile.ProfileData). Every resume-sourced item has a span.
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    experience_months: Mapped[int | None] = mapped_column(Integer)

    # Preferences (AGENTS.md section 6). Versioned with the profile so changes invalidate scores.
    target_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    remote_scope: Mapped[str] = mapped_column(String(16), server_default="none", nullable=False)
    onsite_locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), server_default=text("'{}'"), nullable=False
    )
    open_to: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), server_default=text("'{full_time}'"), nullable=False
    )
    min_salary: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    salary_unknown_policy: Mapped[str] = mapped_column(
        String(16), server_default="include", nullable=False
    )
