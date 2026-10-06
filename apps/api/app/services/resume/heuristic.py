"""Rule-based resume parser. Runs locally with no LLM.

Used when AI parsing is off, unavailable, over budget or failing. It produces the same
ResumeExtraction shape as the LLM, with evidence quoted straight from the text, so it goes
through the same evidence validation.
"""

import re

from app.ai.schemas import (
    ExtractedCertification,
    ExtractedEducation,
    ExtractedExperience,
    ExtractedProject,
    ExtractedSkill,
    ResumeExtraction,
)
from app.utils.dates import DATE_RANGE_RE
from app.utils.text import BULLET_CHARS

_SECTIONS: dict[str, set[str]] = {
    "summary": {"summary", "profile", "professional summary", "about", "about me", "objective",
                "career objective"},
    "skills": {"skills", "technical skills", "key skills", "core skills", "skills & tools",
               "skills and tools", "technologies", "tech stack", "tools", "core competencies"},
    "experience": {"experience", "work experience", "professional experience", "employment",
                   "employment history", "work history", "internships", "internship",
                   "experience & internships"},
    "projects": {"projects", "personal projects", "academic projects", "key projects"},
    "education": {"education", "academic background", "academics", "qualifications",
                  "educational qualifications"},
    "certifications": {"certifications", "certificates", "licenses & certifications",
                       "licenses and certifications", "courses", "certifications & courses"},
    "other": {"achievements", "awards", "interests", "hobbies", "languages", "publications",
              "activities", "extracurricular activities", "references", "volunteering",
              "positions of responsibility"},
}  # fmt: skip

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,16}\d(?!\w)")
_LINK = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com|[\w-]+\.(?:dev|io|me))"
    r"/?[\w./-]*",
    re.IGNORECASE,
)
_INSTITUTION = re.compile(
    r"universit|college|institute|school|academy|iit\b|nit\b|iiit\b|polytechnic", re.IGNORECASE
)
_DEGREE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|bca|mca|mba|b\.?\s?com|"
    r"bachelor[^,|]*|master[^,|]*|ph\.?\s?d|diploma[^,|]*|12th|10th|hsc|ssc)",
    re.IGNORECASE,
)
_SKILL_SPLIT = re.compile(r"\s*(?:,|;|\||•|·|/(?!\w*\.)|\s{2,})\s*")


def _heading(line: str) -> str | None:
    cleaned = line.strip().strip(":").strip()
    if not cleaned or len(cleaned) > 40:
        return None
    key = re.sub(r"\s+", " ", cleaned.lower())
    for section, names in _SECTIONS.items():
        if key in names:
            return section
    return None


def is_section_heading(line: str) -> bool:
    return _heading(line) is not None


def _is_bullet(line: str) -> bool:
    return bool(line) and line[0] in BULLET_CHARS


def _strip_bullet(line: str) -> str:
    return line.lstrip(BULLET_CHARS).strip()


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        heading = _heading(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _skills(lines: list[str]) -> list[ExtractedSkill]:
    skills: list[ExtractedSkill] = []
    for line in lines:
        body = _strip_bullet(line)
        if ":" in body:  # "Languages: Python, Go"
            body = body.split(":", 1)[1]
        for token in _SKILL_SPLIT.split(body):
            token = token.strip(" .")
            if 1 <= len(token) <= 40 and len(token.split()) <= 4 and not token.isdigit():
                skills.append(ExtractedSkill(name=token, evidence=token))
    return skills


def _split_title_company(header: str) -> tuple[str, str] | None:
    header = header.strip(" ,|-–—")
    if re.search(r"\s+at\s+", header):
        title, company = re.split(r"\s+at\s+", header, maxsplit=1)
        return title.strip(" ,|"), company.strip(" ,|")
    parts = [p.strip() for p in re.split(r"\s*(?:\||,|\s[-–—]\s)\s*", header) if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def _experience(lines: list[str]) -> list[ExtractedExperience]:
    entries: list[ExtractedExperience] = []
    for i, line in enumerate(lines):
        if _is_bullet(line):
            continue
        match = DATE_RANGE_RE.search(line)
        if not match:
            continue
        date_text = match.group(0)
        header = (line[: match.start()] + line[match.end() :]).strip(" ,|-–—()")
        evidence = line
        names = _split_title_company(header) if header else None
        if names is None and i > 0 and lines[i - 1].strip() and not _is_bullet(lines[i - 1]):
            # Title/company on the line above, date on its own line.
            previous = lines[i - 1]
            names = _split_title_company(f"{previous} {header}".strip()) or _split_title_company(
                previous
            )
            evidence = f"{previous}\n{line}"
        if names is None:
            continue
        bullets: list[str] = []
        for following in lines[i + 1 :]:
            if DATE_RANGE_RE.search(following) and not _is_bullet(following):
                break
            if _is_bullet(following):
                bullets.append(_strip_bullet(following))
        entries.append(
            ExtractedExperience(
                title=names[0][:200],
                company=names[1][:200],
                date_text=date_text,
                evidence=evidence[:1000],
                bullets=bullets[:40],
            )
        )
    return entries


def _education(lines: list[str]) -> list[ExtractedEducation]:
    entries: list[ExtractedEducation] = []
    for i, line in enumerate(lines):
        if not _INSTITUTION.search(line):
            continue
        institution = re.split(r"\s*(?:\||,|\s[-–—]\s)\s*", _strip_bullet(line))[0]
        institution = DATE_RANGE_RE.sub("", institution).strip(" ,|-–—()") or institution
        # Degree and dates are often on the next line; quote both lines so they are verifiable.
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if following and not _INSTITUTION.search(following) and not _heading(following):
            evidence = f"{line}\n{following}"
        else:
            evidence = line
        dates = DATE_RANGE_RE.search(evidence)
        degree = _DEGREE.search(evidence)
        entries.append(
            ExtractedEducation(
                institution=institution[:200],
                degree=degree.group(0).strip()[:200] if degree else None,
                date_text=dates.group(0) if dates else None,
                evidence=evidence[:1000],
            )
        )
    return entries


def _projects(lines: list[str]) -> list[ExtractedProject]:
    projects: list[ExtractedProject] = []
    for line in lines:
        if not line or _is_bullet(line):
            continue
        name = re.split(r"\s*(?:\||:|\s[-–—]\s)\s*", line)[0].strip()
        if 2 <= len(name) <= 80:
            projects.append(ExtractedProject(name=name, evidence=line[:1000]))
    return projects


def _certifications(lines: list[str]) -> list[ExtractedCertification]:
    certs: list[ExtractedCertification] = []
    for line in lines:
        name = _strip_bullet(line)
        if 3 <= len(name) <= 200:
            certs.append(ExtractedCertification(name=name, evidence=name))
    return certs


def heuristic_extract(text: str) -> ResumeExtraction:
    sections = split_sections(text)
    header = [line for line in sections.get("header", []) if line]
    name = None
    if header:
        first = header[0]
        words = first.split()
        if 1 < len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
            name = first
    email = _EMAIL.search(text)
    phone = _PHONE.search("\n".join(header) or text)
    links = list(dict.fromkeys(m.group(0).rstrip("/.") for m in _LINK.finditer("\n".join(header))))
    return ResumeExtraction(
        name=name,
        email=email.group(0) if email else None,
        phone=phone.group(0).strip() if phone else None,
        links=links[:20],
        skills=_skills(sections.get("skills", []))[:200],
        experience=_experience(sections.get("experience", []))[:50],
        projects=_projects(sections.get("projects", []))[:50],
        education=_education(sections.get("education", []))[:20],
        certifications=_certifications(sections.get("certifications", []))[:50],
    )
