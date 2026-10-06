import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import ScoringConfig

COMPONENTS = ("skills", "experience", "role", "location", "projects", "industry", "preferences")


class Weights(BaseModel):
    skills: int = Field(default=30, ge=0, le=100)
    experience: int = Field(default=20, ge=0, le=100)
    role: int = Field(default=20, ge=0, le=100)
    location: int = Field(default=10, ge=0, le=100)
    projects: int = Field(default=10, ge=0, le=100)
    industry: int = Field(default=5, ge=0, le=100)
    preferences: int = Field(default=5, ge=0, le=100)

    @model_validator(mode="after")
    def _not_all_zero(self) -> "Weights":
        if sum(self.model_dump().values()) == 0:
            raise ValueError("At least one weight must be above zero")
        return self


class Ranking(BaseModel):
    match: float = Field(default=0.70, ge=0, le=1)
    freshness: float = Field(default=0.10, ge=0, le=1)
    salary_fit: float = Field(default=0.10, ge=0, le=1)
    user_priority: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def _sums_to_one(self) -> "Ranking":
        if abs(sum(self.model_dump().values()) - 1.0) > 0.001:
            raise ValueError("Ranking weights must add up to 1")
        return self


class Bands(BaseModel):
    excellent: int = Field(default=90, ge=0, le=100)
    strong: int = Field(default=80, ge=0, le=100)
    good: int = Field(default=70, ge=0, le=100)
    moderate: int = Field(default=60, ge=0, le=100)

    @model_validator(mode="after")
    def _descending(self) -> "Bands":
        if not self.excellent > self.strong > self.good > self.moderate:
            raise ValueError("Bands must be in descending order")
        return self


class ScoringSettings(BaseModel):
    weights: Weights = Field(default_factory=Weights)
    ranking: Ranking = Field(default_factory=Ranking)
    bands: Bands = Field(default_factory=Bands)
    high_priority_threshold: int = Field(default=85, ge=0, le=100)
    llm_top_n: int = Field(default=10, ge=0, le=30)


def label_for(score: int, bands: Bands) -> str:
    if score >= bands.excellent:
        return "Excellent"
    if score >= bands.strong:
        return "Strong"
    if score >= bands.good:
        return "Good"
    if score >= bands.moderate:
        return "Moderate"
    return "Weak"


class ScoringConfigService:
    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def current(self) -> tuple[int, ScoringSettings]:
        row = self._session.scalar(
            select(ScoringConfig).where(
                ScoringConfig.user_id == self._user_id, ScoringConfig.is_current.is_(True)
            )
        )
        if row is None:
            return self._save(ScoringSettings(), version=1)
        return row.version, ScoringSettings.model_validate(row.config)

    def update(self, settings: ScoringSettings) -> tuple[int, ScoringSettings]:
        version, _ = self.current()
        self._session.execute(
            update(ScoringConfig)
            .where(ScoringConfig.user_id == self._user_id)
            .values(is_current=False)
        )
        return self._save(settings, version=version + 1)

    def _save(self, settings: ScoringSettings, *, version: int) -> tuple[int, ScoringSettings]:
        config: dict[str, Any] = settings.model_dump()
        self._session.add(
            ScoringConfig(user_id=self._user_id, version=version, is_current=True, config=config)
        )
        self._session.flush()
        return version, settings
