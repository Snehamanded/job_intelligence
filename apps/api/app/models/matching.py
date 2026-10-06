import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey

EMBEDDING_DIMS = 768


class Embedding(UUIDPrimaryKey, Base):
    """Embedding cache, per user, keyed by content hash and model."""

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", "model", name="uq_embeddings_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # "job" | "profile"
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScoringConfig(UUIDPrimaryKey, Base):
    """Versioned weights, ranking formula and label bands. Each change is a new version."""

    __tablename__ = "scoring_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_scoring_configs_user_version"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobMatch(UUIDPrimaryKey, Timestamps, Base):
    """A job's score for one profile version and one scoring config version."""

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "job_id", "profile_version", "scoring_config_version",
            name="uq_job_matches_key",
        ),
        Index(
            "ix_job_matches_current", "user_id", "profile_version", "scoring_config_version",
            "rank_score",
        ),
    )  # fmt: skip

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_score: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    high_priority: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # {component: {"score", "weight", "method", "detail"}}
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # [{"name", "status", "profile_skills"}]
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_source: Mapped[str] = mapped_column(String(16), nullable=False)  # ai | summary
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # ai | embedding | lexical
    similarity: Mapped[float | None] = mapped_column(Float)
