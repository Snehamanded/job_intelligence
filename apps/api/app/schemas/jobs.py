import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.matching import MatchDetail, MatchSummary


class EligibilityCheckRead(BaseModel):
    name: Literal["employment_type", "location", "salary", "experience"]
    status: Literal["pass", "fail", "unknown"]
    reason: str


class EligibilityRead(BaseModel):
    eligible: bool
    checks: list[EligibilityCheckRead]


class ApplicationRef(BaseModel):
    id: uuid.UUID
    stage: Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]


class SeenOn(BaseModel):
    source: str
    source_job_id: str
    url: str | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    title: str
    company: str
    url: str | None
    locations: list[str]
    remote_type: Literal["remote", "hybrid", "onsite", "unknown"]
    remote_regions: list[str]
    employment_type: Literal["full_time", "contract", "internship", "part_time", "unknown"]
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_period: Literal["year", "month", "hour"] | None
    salary_text: str | None
    salary_unknown: bool
    experience_min_years: int | None
    experience_max_years: int | None
    posted_at: datetime | None
    first_seen_at: datetime
    is_mock: bool
    priority: int
    also_seen_on: list[SeenOn]
    eligibility: EligibilityRead
    match: MatchSummary | None
    application: ApplicationRef | None = None


class JobDetail(JobSummary):
    description_text: str
    match: MatchDetail | None


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    hidden_ineligible: int


class SourceResult(BaseModel):
    source: str
    label: str
    status: Literal["completed", "partial", "failed", "skipped"]
    error: str | None = None
    fetched: int = 0
    kept: int = 0
    new: int = 0
    updated: int = 0
    duplicates: int = 0
    duration_ms: int | None = None
    is_mock: bool = False


class SearchRunCreate(BaseModel):
    keywords: list[str] | None = Field(
        default=None, max_length=10, description="Defaults to your target roles"
    )


class SearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    keywords: list[str]
    source_results: list[SourceResult]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    identifier: str
    display_name: str
    enabled: bool
    last_fetched_at: datetime | None
    created_at: datetime


class JobSourceCreate(BaseModel):
    source: Literal[
        "greenhouse",
        "lever",
        "ashby",
        "remoteok",
        "remotive",
        "weworkremotely",
        "jobspresso",
        "himalayas",
        "adzuna",
    ] = "greenhouse"
    identifier: str = Field(default="", max_length=100, description="Board token, site or country")
    display_name: str | None = Field(default=None, max_length=200)


class ConnectorRead(BaseModel):
    name: str
    label: str
    tier: Literal["A", "B", "C"]
    kind: Literal["real", "import", "mock", "manual_only"]
    enabled: bool
    note: str
    config: Literal["boards", "toggle", "country", "none"]
    attribution: str | None
    category: Literal["general", "india", "startup", "remote", "ats"]


class JobImportRequest(BaseModel):
    """Either a Greenhouse job URL, or a pasted description with title, company and location."""

    url: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=50_000)

    @model_validator(mode="after")
    def _url_or_text(self) -> "JobImportRequest":
        has_text = bool(self.description and self.description.strip())
        if not has_text and not (self.url and self.url.strip()):
            raise ValueError("Provide a Greenhouse job URL or paste the job description")
        if has_text and not (
            self.title and self.title.strip() and self.company and self.company.strip()
        ):
            raise ValueError("Title and company are required with a pasted description")
        if has_text and len(self.description.strip()) < 50:  # type: ignore[union-attr]
            raise ValueError("The description is too short")
        return self


ImportChannel = Literal["email", "whatsapp", "other"]


class ImportBatchCreate(BaseModel):
    """Pasted job alert emails, or WhatsApp messages (copied, or a chat export file's text)."""

    channel: ImportChannel
    text: str = Field(min_length=30, max_length=2_000_000)


class ImportPostResult(BaseModel):
    title: str
    company: str | None = None
    url: str | None = None
    job_id: uuid.UUID | None = None
    status: Literal["new", "updated", "duplicate", "imported", "failed"]
    note: str | None = None


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: ImportChannel
    status: Literal["queued", "running", "completed", "failed"]
    method: Literal["ai", "rules"] | None
    notice: str | None
    error_message: str | None
    results: list[ImportPostResult]
    created_at: datetime
    finished_at: datetime | None
