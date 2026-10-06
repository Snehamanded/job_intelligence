"""Applies the LLM's semantic assessment, re-checking everything it claims in code."""

import re
from dataclasses import dataclass

from app.ai.schemas import JobMatchAssessment
from app.schemas.profile import ProfileData
from app.services.matching.components import Component
from app.services.matching.skills import SkillMatch, canonical, classify

MAX_EXTRA_SKILLS = 5


@dataclass
class Refined:
    skills: list[SkillMatch]
    projects: Component
    industry: Component
    explanation: str


def _in_text(name: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", text, re.I) is not None


def refine(
    assessment: JobMatchAssessment,
    code_skills: list[SkillMatch],
    profile_skills: dict[str, str],
    data: ProfileData,
    job_text: str,
) -> Refined:
    known_profile = {v.lower(): v for v in profile_skills.values()} | {
        k.lower(): v for k, v in profile_skills.items()
    }
    by_name = {s.name.lower(): s for s in assessment.skills}

    skills: list[SkillMatch] = []
    for code in code_skills:
        llm = by_name.get(code.name.lower())
        skills.append(_merge(code, llm.status if llm else None, llm.profile_skill if llm else None,
                             known_profile))  # fmt: skip

    # Skills the LLM says the job needs that code missed: only if the job text really says them.
    have = {s.name.lower() for s in skills}
    for extra in assessment.skills:
        if len(skills) - len(code_skills) >= MAX_EXTRA_SKILLS:
            break
        if extra.name.lower() in have or not _in_text(extra.name, job_text):
            continue
        base = classify([canonical(extra.name)], profile_skills)[0]
        skills.append(_merge(base, extra.status, extra.profile_skill, known_profile))
        have.add(extra.name.lower())

    project_names = {p.name.lower(): p.name for p in data.projects}
    named = [
        project_names[n.lower()] for n in assessment.relevant_projects if n.lower() in project_names
    ]
    if not data.projects:
        projects = Component(50, "unknown", "No projects in your profile to compare")
    elif named:
        projects = Component(assessment.project_relevance, "ai", "Relevant: " + ", ".join(named))
    else:
        # A high score without naming a real project is not trusted.
        projects = Component(
            min(assessment.project_relevance, 20), "ai", "No closely related projects"
        )

    industry = Component(assessment.industry_relevance, "ai", "Industry fit assessed by AI")
    return Refined(skills, projects, industry, " ".join(assessment.explanation.split())[:700])


def _merge(
    code: SkillMatch, llm_status: str | None, llm_profile_skill: str | None, known: dict[str, str]
) -> SkillMatch:
    """Code's `demonstrated` is final. The LLM may mark a skill `related` only by naming a real
    profile skill, may downgrade `related`, and can never create `demonstrated`."""
    if code.status == "demonstrated" or llm_status is None:
        return code
    profile_skill = known.get((llm_profile_skill or "").lower())
    if llm_status in ("demonstrated", "related") and profile_skill:
        return SkillMatch(code.name, "related", [profile_skill])
    if llm_status == "not_demonstrated":
        return SkillMatch(code.name, "not_demonstrated", [])
    return code
