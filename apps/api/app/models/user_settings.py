import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class UserSettings(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Explicit consent before any resume text is sent to a third-party LLM.
    llm_consent: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    llm_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
