"""Turns an extraction into a verified profile.

An item is kept only if its quoted evidence is found in the resume text and the evidence
actually mentions what the item claims. Everything else becomes an UnsupportedClaim, which is
shown to the user and never saved as fact. Spans and dates are computed here, in code.
"""

import re
from datetime import date

from app.ai.schemas import ResumeExtraction
from app.schemas.profile import (
    Bullet,
    Certification,
    Contact,
    Education,
    Experience,
    ItemKind,
    ProfileData,
    Project,
    Skill,
    SourceSpan,
    UnsupportedClaim,
)
from app.services.resume.heuristic import is_section_heading
from app.utils.dates import DateRange, experience_months, parse_date_range
from app.utils.text import TextIndex, contains_folded

NOT_IN_RESUME = "Quoted text was not found in the resume"
NOT_IN_EVIDENCE = "The quoted text does not mention it"
NOT_IN_ITEM = "Not mentioned in this item's part of the resume"

# How far past its quote an item's own block may extend (until the next item or heading).
MAX_BLOCK_CHARS = 600

# Common abbreviations, so "JS" evidence can support the skill "JavaScript".
SKILL_ALIASES: dict[str, set[str]] = {
    "javascript": {"js", "ecmascript"},
    "typescript": {"ts"},
    "kubernetes": {"k8s"},
    "postgresql": {"postgres", "psql"},
    "machine learning": {"ml"},
    "artificial intelligence": {"ai"},
    "natural language processing": {"nlp"},
    "amazon web services": {"aws"},
    "google cloud platform": {"gcp", "google cloud"},
    "continuous integration": {"ci", "ci/cd"},
    "node.js": {"node", "nodejs"},
    "react": {"react.js", "reactjs"},
    "next.js": {"nextjs"},
    "c++": {"cpp"},
    "c#": {"csharp"},
}


def _mentions(evidence: str, term: str) -> bool:
    folded_term = TextIndex.fold(term)
    if not folded_term:
        return False
    folded = TextIndex.fold(evidence)
    # Word-ish boundary so "Go" isn't supported by "Google" and "R" isn't supported by "React".
    pattern = rf"(?<![a-z0-9]){re.escape(folded_term)}(?![a-z0-9])"
    return re.search(pattern, folded) is not None


def skill_supported(name: str, evidence: str) -> bool:
    if _mentions(evidence, name):
        return True
    key = TextIndex.fold(name)
    aliases = SKILL_ALIASES.get(key, set())
    aliases |= {canonical for canonical, alts in SKILL_ALIASES.items() if key in alts}
    return any(_mentions(evidence, alias) for alias in aliases)


def _if_quoted(value: str | None, evidence: str) -> str | None:
    """Keep an optional detail only if the item's own quote contains it."""
    return value if value and contains_folded(evidence, value) else None


class EvidenceValidator:
    def __init__(self, text: str, today: date | None = None) -> None:
        self.index = TextIndex(text)
        self.today = today
        self.unsupported: list[UnsupportedClaim] = []

    def _reject(self, kind: ItemKind, label: str, evidence: str | None, reason: str) -> None:
        self.unsupported.append(
            UnsupportedClaim(kind=kind, label=label[:300], evidence=evidence, reason=reason)
        )

    def _span(self, quote: str | None) -> SourceSpan | None:
        found = self.index.find(quote) if quote else None
        return SourceSpan(start=found[0], end=found[1]) if found else None

    def _block(self, span: SourceSpan, sibling_starts: list[int]) -> str:
        """The item's own part of the resume: from its quote up to the next sibling item, the
        next section heading, or MAX_BLOCK_CHARS. Optional details may be supported here; the
        item's core claim must still be in its quote."""
        text = self.index.text
        limit = min([s for s in sibling_starts if s > span.start] + [span.end + MAX_BLOCK_CHARS])
        limit = min(limit, len(text))
        # Finish the quote's last line, then take whole lines until a section heading.
        end = text.find("\n", span.end)
        if end == -1 or end >= limit:
            return text[span.start : limit]
        while end < limit:
            next_newline = text.find("\n", end + 1)
            line_end = len(text) if next_newline == -1 else next_newline
            if is_section_heading(text[end + 1 : line_end]):
                break
            end = line_end
        return text[span.start : min(end, limit)]

    def _dates(self, date_text: str | None) -> tuple[str | None, DateRange | None]:
        """Accept date text only if it is in the resume, then parse it in code."""
        if not date_text or not self.index.contains(date_text):
            return None, None
        return date_text, parse_date_range(date_text, self.today)

    def validate(self, extraction: ResumeExtraction) -> ProfileData:
        self.unsupported = []
        data = ProfileData(
            contact=self._contact(extraction),
            skills=self._skills(extraction),
            experience=self._experience(extraction),
            projects=self._projects(extraction),
            education=self._education(extraction),
            certifications=self._certifications(extraction),
        )
        data.unsupported = self.unsupported
        return data

    def _contact(self, ex: ResumeExtraction) -> Contact:
        contact = Contact()
        for field in ("name", "email", "phone", "location"):
            value = getattr(ex, field)
            if not value:
                continue
            if self.index.contains(value):
                setattr(contact, field, value)
            else:
                self._reject("contact", f"{field}: {value}", value, NOT_IN_RESUME)
        for link in ex.links:
            if self.index.contains(link):
                contact.links.append(link)
            else:
                self._reject("contact", f"link: {link}", link, NOT_IN_RESUME)
        return contact

    def _skills(self, ex: ResumeExtraction) -> list[Skill]:
        skills: list[Skill] = []
        seen: set[str] = set()
        for item in ex.skills:
            span = self._span(item.evidence)
            if span is None:
                self._reject("skill", item.name, item.evidence, NOT_IN_RESUME)
            elif not skill_supported(item.name, item.evidence):
                self._reject("skill", item.name, item.evidence, NOT_IN_EVIDENCE)
            elif TextIndex.fold(item.name) not in seen:
                seen.add(TextIndex.fold(item.name))
                skills.append(Skill(name=item.name, evidence=item.evidence, source_span=span))
        return skills

    def _bullets(self, bullets: list[str]) -> list[Bullet]:
        kept: list[Bullet] = []
        for text in bullets:
            span = self._span(text)
            if span is None:
                self._reject("bullet", text, text, NOT_IN_RESUME)
            else:
                kept.append(Bullet(text=text, evidence=text, source_span=span))
        return kept

    def _experience(self, ex: ResumeExtraction) -> list[Experience]:
        kept: list[Experience] = []
        for item in ex.experience:
            label = f"{item.title} at {item.company}"
            span = self._span(item.evidence)
            if span is None:
                self._reject("experience", label, item.evidence, NOT_IN_RESUME)
                continue
            ev = item.evidence
            if not (contains_folded(ev, item.title) and contains_folded(ev, item.company)):
                self._reject("experience", label, ev, NOT_IN_EVIDENCE)
                continue
            date_text, dates = self._dates(item.date_text)
            kept.append(
                Experience(
                    title=item.title,
                    company=item.company,
                    location=_if_quoted(item.location, ev),
                    date_text=date_text,
                    start=str(dates.start) if dates else None,
                    end=str(dates.end) if dates and dates.end else None,
                    is_current=bool(dates and dates.is_current),
                    evidence=ev,
                    source_span=span,
                    bullets=self._bullets(item.bullets),
                )
            )
        return kept

    def _projects(self, ex: ResumeExtraction) -> list[Project]:
        kept: list[Project] = []
        spans = [self._span(item.evidence) for item in ex.projects]
        starts = [sp.start for sp in spans if sp]
        for item, span in zip(ex.projects, spans, strict=True):
            if span is None:
                self._reject("project", item.name, item.evidence, NOT_IN_RESUME)
                continue
            if not contains_folded(item.evidence, item.name):
                self._reject("project", item.name, item.evidence, NOT_IN_EVIDENCE)
                continue
            block = self._block(span, starts)
            description = _if_quoted(item.description, block)
            technologies = [t for t in item.technologies if skill_supported(t, block)]
            for tech in item.technologies:
                if tech not in technologies:
                    self._reject("skill", f"{tech} (in project {item.name})", None, NOT_IN_ITEM)
            kept.append(
                Project(
                    name=item.name,
                    description=description,
                    technologies=technologies,
                    evidence=item.evidence,
                    source_span=span,
                )
            )
        return kept

    def _education(self, ex: ResumeExtraction) -> list[Education]:
        kept: list[Education] = []
        spans = [self._span(item.evidence) for item in ex.education]
        starts = [sp.start for sp in spans if sp]
        for item, span in zip(ex.education, spans, strict=True):
            if span is None:
                self._reject("education", item.institution, item.evidence, NOT_IN_RESUME)
                continue
            ev = item.evidence
            if not contains_folded(ev, item.institution):
                self._reject("education", item.institution, ev, NOT_IN_EVIDENCE)
                continue
            block = self._block(span, starts)
            date_text, dates = self._dates(
                item.date_text if _if_quoted(item.date_text, block) else None
            )
            kept.append(
                Education(
                    institution=item.institution,
                    degree=_if_quoted(item.degree, block),
                    field_of_study=_if_quoted(item.field_of_study, block),
                    date_text=date_text,
                    start=str(dates.start) if dates else None,
                    end=str(dates.end) if dates and dates.end else None,
                    evidence=ev,
                    source_span=span,
                )
            )
        return kept

    def _certifications(self, ex: ResumeExtraction) -> list[Certification]:
        kept: list[Certification] = []
        for item in ex.certifications:
            span = self._span(item.evidence)
            if span is None:
                self._reject("certification", item.name, item.evidence, NOT_IN_RESUME)
            elif not contains_folded(item.evidence, item.name):
                self._reject("certification", item.name, item.evidence, NOT_IN_EVIDENCE)
            else:
                kept.append(
                    Certification(
                        name=item.name,
                        issuer=_if_quoted(item.issuer, item.evidence),
                        evidence=item.evidence,
                        source_span=span,
                    )
                )
        return kept


def profile_experience_months(data: ProfileData, today: date | None = None) -> int | None:
    """Total experience in months from roles with parseable dates, overlaps counted once."""
    ranges = [r for e in data.experience if (r := parse_date_range(e.date_text, today))]
    return experience_months(ranges, today) if ranges else None
