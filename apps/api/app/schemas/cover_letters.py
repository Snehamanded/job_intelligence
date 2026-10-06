import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SentenceKind = Literal["claim", "company", "connective"]
Tone = Literal["professional", "warm", "concise"]
Length = Literal["short", "medium"]


class Sentence(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=600)
    kind: SentenceKind
    sources: list[str] = Field(default_factory=list)  # resume item ids (claims)
    job_quote: str | None = None  # verbatim from the posting (company facts)
    source: Literal["ai", "template", "user"]
    status: Literal["proposed", "unsupported"]
    issues: list[str] = Field(default_factory=list)
    included: bool = True


class Paragraph(BaseModel):
    id: str
    sentences: list[Sentence] = Field(default_factory=list)


class LetterContent(BaseModel):
    """Saved letter: only included sentences, with their labels kept for traceability."""

    paragraphs: list[Paragraph]
    signature: str | None = None


class CoverLetterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    name: str
    job_id: uuid.UUID | None
    resume_version_id: uuid.UUID | None
    job_title: str
    company: str
    tone: Tone
    length: Length
    status: Literal["generating", "ready", "failed", "saved"]
    method: Literal["ai", "template"]
    notice: str | None
    created_at: datetime
    updated_at: datetime


class CoverLetterDetail(CoverLetterSummary):
    paragraphs: list[Paragraph]
    preview: list[str]  # included sentences joined per paragraph
    signature: str | None


class CoverLetterCreate(BaseModel):
    job_id: uuid.UUID
    resume_version_id: uuid.UUID | None = None
    tone: Tone = "professional"
    length: Length = "medium"


class SentenceUpdate(BaseModel):
    included: bool | None = None
    text: str | None = Field(default=None, min_length=1, max_length=600)


class NewSentence(BaseModel):
    paragraph_id: str = Field(max_length=20)
    text: str = Field(min_length=1, max_length=600)


class SentencesUpdate(BaseModel):
    updates: dict[str, SentenceUpdate] = Field(default_factory=dict, max_length=200)
    add: list[NewSentence] = Field(default_factory=list, max_length=20)


class CoverLetterSave(BaseModel):
    name: str | None = Field(default=None, max_length=200)
