"""Code checks for cover-letter sentences (AGENTS.md section 3). Any issue = UNSUPPORTED."""

from app.services.matching.skills import find_skills
from app.services.tailoring.checks import numbers
from app.utils.text import TextIndex


def check_claim(text: str, sources: list[str], item_texts: dict[str, str]) -> list[str]:
    known = [s for s in sources if s in item_texts]
    if not known:
        return ["A statement about you that doesn't cite anything on your resume"]
    cited = "\n".join(item_texts[s] for s in known)
    issues = [
        f"Adds the number “{n}”, which the cited resume items don't have"
        for n in sorted(numbers(text) - numbers(cited))
    ]
    issues += [
        f"Mentions {skill}, which the cited resume items don't"
        for skill in sorted(set(find_skills(text)) - set(find_skills(cited)))
    ]
    return issues


def check_company(text: str, quote: str | None, job_text: str) -> list[str]:
    if not quote or not quote.strip():
        return ["A statement about the company without a quote from the job posting"]
    if not TextIndex(job_text).contains(quote):
        return ["The quoted text isn't in the job posting"]
    issues = [
        f"Adds the number “{n}”, which the quoted posting text doesn't have"
        for n in sorted(numbers(text) - numbers(quote))
    ]
    issues += [
        f"Mentions {skill}, which the quoted posting text doesn't"
        for skill in sorted(set(find_skills(text)) - set(find_skills(quote)))
    ]
    return issues


def check_connective(text: str) -> list[str]:
    issues = []
    if numbers(text):
        issues.append("States a number without a source")
    skills = find_skills(text)
    if skills:
        issues.append("Mentions " + ", ".join(skills) + " without citing your resume")
    return issues
