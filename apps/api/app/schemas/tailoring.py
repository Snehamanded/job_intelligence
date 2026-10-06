import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import Contact, SourceSpan

# --- the tailored document: every item traces back to the verified resume -------------


class DocBullet(BaseModel):
    id: str
    text: str
    original_text: str
    source_span: SourceSpan | None  # None only for items the user added to their profile
    ai_changed: bool = False


class DocRole(BaseModel):
    id: str
    title: str
    company: str
    location: str | None = None
    date_text: str | None = None
    source_span: SourceSpan | None = None
    bullets: list[DocBullet] = Field(default_factory=list)


class DocSkill(BaseModel):
    id: str
    name: str
    source_span: SourceSpan | None = None


class DocProject(BaseModel):
    id: str
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    source_span: SourceSpan | None = None


class DocEducation(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    date_text: str | None = None
    source_span: SourceSpan | None = None


class DocCertification(BaseModel):
    name: str
    issuer: str | None = None
    source_span: SourceSpan | None = None


class SummarySentence(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    sources: list[str] = Field(default_factory=list, max_length=10)  # ids of cited resume items


class ResumeDocument(BaseModel):
    contact: Contact = Field(default_factory=Contact)
    summary: list[SummarySentence] = Field(default_factory=list)
    skills: list[DocSkill] = Field(default_factory=list)
    experience: list[DocRole] = Field(default_factory=list)
    projects: list[DocProject] = Field(default_factory=list)
    education: list[DocEducation] = Field(default_factory=list)
    certifications: list[DocCertification] = Field(default_factory=list)


# --- proposed changes -------------------------------------------------------------------

ChangeKind = Literal["skills_order", "bullets_order", "bullet_rewrite", "summary"]
Decision = Literal["pending", "accepted", "rejected"]


class Change(BaseModel):
    id: str
    kind: ChangeKind
    source: Literal["ai", "rules"]
    status: Literal["proposed", "unsupported"]
    decision: Decision = "pending"
    title: str
    reason: str | None = None
    issues: list[str] = Field(default_factory=list)
    skill_ids: list[str] | None = None  # skills_order
    role_id: str | None = None  # bullets_order, bullet_rewrite
    bullet_ids: list[str] | None = None  # bullets_order
    bullet_id: str | None = None  # bullet_rewrite
    before: str | None = None
    after: str | None = None
    sentences: list[SummarySentence] | None = None  # summary
    labels: list[str] | None = None  # display names for skill_ids / bullet_ids, in order


class SkillGap(BaseModel):
    name: str
    status: Literal["related", "not_demonstrated"]
    profile_skills: list[str] = Field(default_factory=list)


class TailoringSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    name: str
    job_id: uuid.UUID | None
    job_title: str
    company: str
    status: Literal["generating", "ready", "failed", "saved"]
    method: Literal["ai", "rules"]
    notice: str | None
    created_at: datetime
    updated_at: datetime


class TailoringDetail(TailoringSummary):
    changes: list[Change]
    preview: ResumeDocument | None
    skill_gaps: list[SkillGap]


class TailoringCreate(BaseModel):
    job_id: uuid.UUID


class DecisionsUpdate(BaseModel):
    decisions: dict[str, Literal["accepted", "rejected", "pending"]] = Field(max_length=200)


class TailoringSave(BaseModel):
    name: str | None = Field(default=None, max_length=200)
