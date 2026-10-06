from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.matching.config import ScoringSettings


class MatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_score: int
    rank_score: float
    label: Literal["Excellent", "Strong", "Good", "Moderate", "Weak"]
    high_priority: bool
    method: Literal["ai", "embedding", "lexical"]


class ComponentRead(BaseModel):
    score: int
    weight: int
    method: Literal["code", "ai", "embedding", "unknown"]
    detail: str


class SkillRead(BaseModel):
    name: str
    status: Literal["demonstrated", "related", "not_demonstrated"]
    profile_skills: list[str]


class MatchDetail(MatchSummary):
    components: dict[str, ComponentRead]
    skills: list[SkillRead]
    explanation: str
    explanation_source: Literal["ai", "summary"]
    similarity: float | None
    profile_version: int
    scoring_config_version: int


class ScoringConfigRead(BaseModel):
    version: int
    settings: ScoringSettings


class MatchStatus(BaseModel):
    profile_version: int | None
    scoring_config_version: int
    total_jobs: int
    scored_jobs: int
    ai_enabled: bool
    note: str | None


class JobPriorityUpdate(BaseModel):
    priority: int = Field(ge=0, le=2, description="0 low, 1 normal, 2 high")
