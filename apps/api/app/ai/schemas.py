"""Shapes the LLM must return. Validated with Pydantic before anything is used.

Every item quotes `evidence` verbatim from the resume. Spans are computed in code, never by the LLM.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Short = Field(min_length=1, max_length=200)
Quote = Field(min_length=1, max_length=1000)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class ExtractedSkill(_Strict):
    name: str = Short
    evidence: str = Quote


class ExtractedExperience(_Strict):
    title: str = Short
    company: str = Short
    location: str | None = Field(default=None, max_length=200)
    date_text: str | None = Field(default=None, max_length=100)
    evidence: str = Quote
    bullets: list[str] = Field(default_factory=list, max_length=40)


class ExtractedProject(_Strict):
    name: str = Short
    description: str | None = Field(default=None, max_length=1000)
    technologies: list[str] = Field(default_factory=list, max_length=40)
    evidence: str = Quote


class ExtractedEducation(_Strict):
    institution: str = Short
    degree: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    date_text: str | None = Field(default=None, max_length=100)
    evidence: str = Quote


class ExtractedCertification(_Strict):
    name: str = Short
    issuer: str | None = Field(default=None, max_length=200)
    evidence: str = Quote


class ResumeExtraction(_Strict):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    links: list[str] = Field(default_factory=list, max_length=20)
    skills: list[ExtractedSkill] = Field(default_factory=list, max_length=200)
    experience: list[ExtractedExperience] = Field(default_factory=list, max_length=50)
    projects: list[ExtractedProject] = Field(default_factory=list, max_length=50)
    education: list[ExtractedEducation] = Field(default_factory=list, max_length=20)
    certifications: list[ExtractedCertification] = Field(default_factory=list, max_length=50)


class MatchedSkill(_Strict):
    name: str = Short
    status: Literal["demonstrated", "related", "not_demonstrated"]
    profile_skill: str | None = Field(default=None, max_length=200)


class JobMatchAssessment(_Strict):
    skills: list[MatchedSkill] = Field(default_factory=list, max_length=40)
    project_relevance: int = Field(ge=0, le=100)
    relevant_projects: list[str] = Field(default_factory=list, max_length=10)
    industry_relevance: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=1200)


class TailorRoleOrder(_Strict):
    role_id: str = Field(max_length=20)
    bullet_ids: list[str] = Field(default_factory=list, max_length=40)


class TailorRewrite(_Strict):
    bullet_id: str = Field(max_length=20)
    text: str = Field(min_length=1, max_length=600)
    reason: str = Field(default="", max_length=200)


class TailorSentence(_Strict):
    text: str = Field(min_length=1, max_length=400)
    sources: list[str] = Field(default_factory=list, max_length=10)


class TailorSuggestions(_Strict):
    skills_order: list[str] = Field(default_factory=list, max_length=300)
    roles: list[TailorRoleOrder] = Field(default_factory=list, max_length=50)
    rewrites: list[TailorRewrite] = Field(default_factory=list, max_length=60)
    summary: list[TailorSentence] = Field(default_factory=list, max_length=2)


class VerifyResult(_Strict):
    change_id: str = Field(max_length=60)
    supported: bool
    problems: list[str] = Field(default_factory=list, max_length=10)


class VerifyReport(_Strict):
    results: list[VerifyResult] = Field(default_factory=list, max_length=100)


class LetterSentence(_Strict):
    text: str = Field(min_length=1, max_length=600)
    kind: Literal["claim", "company", "connective"]
    sources: list[str] = Field(default_factory=list, max_length=10)
    job_quote: str | None = Field(default=None, max_length=600)


class LetterParagraph(_Strict):
    sentences: list[LetterSentence] = Field(default_factory=list, max_length=8)


class LetterDraft(_Strict):
    paragraphs: list[LetterParagraph] = Field(default_factory=list, max_length=5)


class SentenceCheck(_Strict):
    sentence_id: str = Field(max_length=20)
    supported: bool
    problems: list[str] = Field(default_factory=list, max_length=10)


class LetterVerifyReport(_Strict):
    results: list[SentenceCheck] = Field(default_factory=list, max_length=60)
