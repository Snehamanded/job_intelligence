import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Stage = Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]
InterviewKind = Literal[
    "phone_screen", "technical", "system_design", "behavioral", "hiring_manager", "onsite", "other"
]
Outcome = Literal["pending", "passed", "failed", "cancelled"]


class ChecklistItem(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    done: bool = False


class ApplicationCreate(BaseModel):
    """Track a job in the app (job_id), or one applied to elsewhere (title + company)."""

    job_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2000)
    stage: Stage = "saved"
    applied_at: date | None = None

    @model_validator(mode="after")
    def _job_or_details(self) -> "ApplicationCreate":
        if self.job_id is None and not (
            self.title and self.title.strip() and self.company and self.company.strip()
        ):
            raise ValueError("Choose a job, or enter the title and company")
        return self

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value and not value.strip().startswith(("https://", "http://")):
            raise ValueError("The link must start with http:// or https://")
        return value.strip() if value else None


class ApplicationUpdate(BaseModel):
    stage: Stage | None = None
    position: int | None = Field(default=None, ge=0, le=100_000)
    applied_at: date | None = None
    next_action: str | None = Field(default=None, max_length=300)
    next_action_date: date | None = None


class ApplicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    location: str | None
    url: str | None
    source: str
    match_score: int | None
    match_label: str | None
    stage: Stage
    position: int
    applied_at: date | None
    closed_at: datetime | None
    next_action: str | None
    next_action_date: date | None
    created_at: datetime
    updated_at: datetime
    next_interview_at: datetime | None = None
    notes_count: int = 0


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    from_stage: Stage | None
    to_stage: Stage | None
    detail: str | None
    created_at: datetime


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    created_at: datetime
    updated_at: datetime


class InterviewCreate(BaseModel):
    scheduled_at: datetime
    kind: InterviewKind = "other"
    location: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=30)

    @field_validator("scheduled_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Include a timezone with the interview time")
        return value


class InterviewUpdate(BaseModel):
    scheduled_at: datetime | None = None
    kind: InterviewKind | None = None
    location: str | None = Field(default=None, max_length=500)
    outcome: Outcome | None = None
    notes: str | None = Field(default=None, max_length=5000)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=30)


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    scheduled_at: datetime
    kind: InterviewKind
    location: str | None
    outcome: Outcome
    notes: str | None
    checklist: list[ChecklistItem]


class UpcomingInterview(InterviewRead):
    title: str
    company: str


class ApplicationDetail(ApplicationSummary):
    notes: list[NoteRead]
    interviews: list[InterviewRead]
    events: list[EventRead]


class Rates(BaseModel):
    applied: int
    responded: int
    interviews: int
    offers: int
    response_rate: float | None
    interview_rate: float | None
    offer_rate: float | None


class GroupRates(Rates):
    group: str


class WeekCount(BaseModel):
    week_start: date
    applied: int


class Analytics(BaseModel):
    stage_counts: dict[str, int]
    funnel: dict[str, int]  # applications that ever reached each stage
    overall: Rates
    by_source: list[GroupRates]
    by_match_band: list[GroupRates]
    weekly: list[WeekCount]
