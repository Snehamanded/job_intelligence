"""Deterministic score components (AGENTS.md section 5). Each returns 0-100 plus a reason."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.models import Job
from app.schemas.profile import ProfileData
from app.services.jobs.eligibility import Eligibility
from app.services.jobs.normalize import title_words
from app.services.matching.skills import canonical, find_skills

Method = Literal["code", "ai", "embedding", "unknown"]


@dataclass
class Component:
    score: int
    method: Method
    detail: str


def _check(eligibility: Eligibility, name: str) -> str:
    return next(c.status for c in eligibility.checks if c.name == name)


# Typical years implied by a title when the posting states none. Highest match wins.
_SENIORITY = [
    (re.compile(r"\b(intern|internship|trainee)\b", re.I), 0, "Intern-level"),
    (re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|fresher)\b", re.I), 0, "Junior"),
    (re.compile(r"\b(intermediate|mid[- ]level)\b", re.I), 2, "Mid-level"),
    (re.compile(r"\b(senior|sr\.?)\b", re.I), 5, "Senior"),
    (re.compile(r"\b(staff|lead|principal)\b", re.I), 8, "Staff/lead"),
    (
        re.compile(
            r"\b(engineering|development|software) manager\b|\bmanager,? engineering\b", re.I
        ),
        8,
        "Engineering manager",
    ),
    (re.compile(r"\b(director|head of|vp|vice president|chief)\b", re.I), 10, "Director-level"),
]


def implied_years(title: str) -> tuple[int, str] | None:
    hits = [(years, label) for pattern, years, label in _SENIORITY if pattern.search(title)]
    return max(hits) if hits else None


def experience(job: Job, months: int | None) -> Component:
    min_years, max_years, inferred = job.experience_min_years, job.experience_max_years, None
    if min_years is None:
        implied = implied_years(job.title)
        if implied is None:
            return Component(70, "code", "No experience requirement stated")
        min_years, inferred = implied[0], implied[1]
    if months is None:
        return Component(50, "unknown", "Your experience is unknown")
    years = months / 12
    need = (
        f"{inferred} title (usually {min_years}+ years, inferred)"
        if inferred
        else f"Needs {min_years}+ years"
    )
    gap = min_years - years
    if gap <= 0:
        if max_years is not None and years > max_years + 3:
            return Component(80, "code", f"You have more than the {max_years} years asked")
        return Component(100, "code", f"{need}; you have about {years:.1f}")
    return Component(max(0, round(100 - gap * 30)), "code", f"{need}; you have about {years:.1f}")


def location(eligibility: Eligibility) -> Component:
    check = next(c for c in eligibility.checks if c.name == "location")
    return Component({"pass": 100, "unknown": 50, "fail": 0}[check.status], "code", check.reason)


def preferences(eligibility: Eligibility) -> Component:
    emp = {"pass": 100, "unknown": 60, "fail": 0}[_check(eligibility, "employment_type")]
    sal = {"pass": 100, "unknown": 50, "fail": 0}[_check(eligibility, "salary")]
    return Component(round((emp + sal) / 2), "code", "Employment type and salary fit")


def scale_similarity(similarity: float, floor: float, ceiling: float) -> int:
    return round(100 * min(1.0, max(0.0, (similarity - floor) / (ceiling - floor))))


def role(job: Job, target_roles: list[str], data: ProfileData, similarity: int | None) -> Component:
    titles = [*target_roles, *(e.title for e in data.experience)]
    if not titles:
        if similarity is not None:
            return Component(similarity, "embedding", "Similarity of the job to your profile")
        return Component(50, "unknown", "Add target roles to compare job titles")
    job_words = set(title_words(job.title))
    best, best_title = 0.0, titles[0]
    for title in titles:
        words = title_words(title)
        if words:
            overlap = sum(w in job_words for w in words) / len(words)
            if overlap > best:
                best, best_title = overlap, title
    overlap_score = round(best * 100)
    detail = f"Title is close to “{best_title}”" if best >= 0.5 else "Title differs from your roles"
    if similarity is None:
        return Component(overlap_score, "code", detail)
    return Component(round(0.6 * overlap_score + 0.4 * similarity), "embedding", detail)


def projects_lexical(job_skills: list[str], data: ProfileData) -> Component:
    if not data.projects:
        return Component(50, "unknown", "No projects in your profile to compare")
    wanted = set(job_skills)
    best_name, best = data.projects[0].name, 0
    for project in data.projects:
        text = " ".join([project.name, project.description or "", ", ".join(project.technologies)])
        overlap = len(wanted & {canonical(s) for s in [*project.technologies, *find_skills(text)]})
        if overlap > best:
            best_name, best = project.name, overlap
    if best == 0:
        return Component(20, "code", "Your projects don't use this job's main skills")
    return Component(min(100, 40 * best), "code", f"“{best_name}” uses {best} of the job's skills")


def industry_unknown() -> Component:
    return Component(50, "unknown", "Industry fit is assessed only with AI processing on")


def freshness(job: Job, now: datetime | None = None) -> float:
    """1.0 for the first week, falling to 0 at 60 days. Unknown dates count as 0.5."""
    if job.posted_at is None:
        return 0.5
    days = ((now or datetime.now(UTC)) - job.posted_at).total_seconds() / 86400
    if days <= 7:
        return 1.0
    return max(0.0, 1 - (days - 7) / 53)


def salary_fit(eligibility: Eligibility, min_salary_set: bool) -> float:
    status = _check(eligibility, "salary")
    if status == "fail":
        return 0.0
    if status == "pass" and min_salary_set:
        return 1.0
    return 0.5


def profile_skill_map(data: ProfileData) -> dict[str, str]:
    """Canonical skill -> how it appears in the verified profile (skills, bullets, projects)."""
    found: dict[str, str] = {}
    for skill in data.skills:
        found.setdefault(canonical(skill.name), skill.name)
    for project in data.projects:
        for tech in project.technologies:
            found.setdefault(canonical(tech), tech)
    evidence = [b.text for e in data.experience for b in e.bullets]
    evidence += [p.description or "" for p in data.projects]
    for name in find_skills("\n".join(evidence)):
        found.setdefault(name, f"{name} (in your experience)")
    return found


def strip_markup(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
