import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ItemSource = Literal["resume", "user"]
RemoteScope = Literal["none", "india", "worldwide"]
EmploymentType = Literal["full_time", "contract", "internship", "part_time"]


class SourceSpan(BaseModel):
    """Character offsets [start, end) into the resume's extracted text."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class _Item(BaseModel):
    # `resume` items must quote the resume; the server recomputes `source_span` from `evidence`.
    source: ItemSource = "resume"
    evidence: str | None = Field(default=None, max_length=1000)
    source_span: SourceSpan | None = None


class Skill(_Item):
    name: str = Field(min_length=1, max_length=100)


class Bullet(_Item):
    text: str = Field(min_length=1, max_length=1000)


class Experience(_Item):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    date_text: str | None = Field(default=None, max_length=100)
    start: str | None = Field(default=None, description="YYYY-MM, parsed in code from date_text")
    end: str | None = None
    is_current: bool = False
    bullets: list[Bullet] = Field(default_factory=list, max_length=40)


class Project(_Item):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    technologies: list[str] = Field(default_factory=list, max_length=40)


class Education(_Item):
    institution: str = Field(min_length=1, max_length=200)
    degree: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    date_text: str | None = Field(default=None, max_length=100)
    start: str | None = None
    end: str | None = None


class Certification(_Item):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)


class Contact(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    links: list[str] = Field(default_factory=list, max_length=20)


ItemKind = Literal[
    "contact", "skill", "experience", "bullet", "project", "education", "certification"
]


class UnsupportedClaim(BaseModel):
    """A claim the extractor made that the resume does not support. Never saved as fact."""

    kind: ItemKind
    label: str = Field(max_length=300)
    evidence: str | None = Field(default=None, max_length=1000)
    reason: str = Field(max_length=200)


class ProfileData(BaseModel):
    contact: Contact = Field(default_factory=Contact)
    skills: list[Skill] = Field(default_factory=list, max_length=300)
    experience: list[Experience] = Field(default_factory=list, max_length=50)
    projects: list[Project] = Field(default_factory=list, max_length=50)
    education: list[Education] = Field(default_factory=list, max_length=20)
    certifications: list[Certification] = Field(default_factory=list, max_length=50)
    unsupported: list[UnsupportedClaim] = Field(default_factory=list, max_length=500)


def _default_open_to() -> list[EmploymentType]:
    return ["full_time"]


class Preferences(BaseModel):
    target_roles: list[str] = Field(default_factory=list, max_length=10)
    remote_scope: RemoteScope = "none"
    onsite_locations: list[str] = Field(default_factory=list, max_length=20)
    open_to: list[EmploymentType] = Field(default_factory=_default_open_to, min_length=1)
    min_salary: int | None = Field(default=None, ge=0, le=1_000_000_000)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    salary_unknown_policy: Literal["include", "exclude"] = "include"

    @field_validator("target_roles")
    @classmethod
    def _clean_roles(cls, roles: list[str]) -> list[str]:
        cleaned: list[str] = []
        for role in roles:
            role = " ".join(role.split())
            if not role:
                continue
            if len(role) > 100:
                raise ValueError("Each target role must be at most 100 characters")
            if role.lower() not in {r.lower() for r in cleaned}:
                cleaned.append(role)
        return cleaned

    @field_validator("open_to")
    @classmethod
    def _dedupe_open_to(cls, values: list[EmploymentType]) -> list[EmploymentType]:
        return list(dict.fromkeys(values))

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @model_validator(mode="after")
    def _salary_needs_currency(self) -> "Preferences":
        if self.min_salary is not None and self.currency is None:
            raise ValueError("currency is required when min_salary is set")
        return self


class ProfileRead(BaseModel):
    id: uuid.UUID
    version: int
    origin: Literal["parsed", "edited"]
    parse_method: Literal["llm", "heuristic"] | None
    resume_id: uuid.UUID | None
    experience_months: int | None
    data: ProfileData
    preferences: Preferences
    created_at: datetime


class ProfileVersionSummary(BaseModel):
    id: uuid.UUID
    version: int
    is_current: bool
    origin: Literal["parsed", "edited"]
    parse_method: Literal["llm", "heuristic"] | None
    resume_id: uuid.UUID | None
    created_at: datetime


class ProfileUpdate(BaseModel):
    data: ProfileData
    preferences: Preferences
