"""Code checks on AI rewrites (AGENTS.md section 3). Any issue makes a change UNSUPPORTED."""

import re

from app.services.matching.skills import find_skills

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MAX_GROWTH = 1.6
MAX_EXTRA_CHARS = 80


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def check_rewrite(original: str, rewrite: str, role_text: str) -> list[str]:
    """Problems with a bullet rewrite. Empty list means the code checks passed."""
    issues: list[str] = []
    if not rewrite.strip():
        return ["The rewrite is empty"]
    for n in sorted(numbers(rewrite) - numbers(original)):
        issues.append(f"Adds the number “{n}”, which the original bullet doesn't have")
    for skill in sorted(set(find_skills(rewrite)) - set(find_skills(role_text))):
        issues.append(f"Mentions {skill}, which this role on your resume doesn't")
    if len(rewrite) > max(len(original) * MAX_GROWTH, len(original) + MAX_EXTRA_CHARS):
        issues.append("Much longer than the original, so it likely adds claims")
    return issues


def check_summary_sentence(text: str, sources: list[str], item_texts: dict[str, str]) -> list[str]:
    known = [s for s in sources if s in item_texts]
    if not known:
        return ["Doesn't cite any item on your resume"]
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
