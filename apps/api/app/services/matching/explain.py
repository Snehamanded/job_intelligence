from app.services.matching.skills import SkillMatch


def summary(skills: list[SkillMatch], experience_detail: str, location_detail: str) -> str:
    """Code-written explanation, used when there is no AI explanation."""
    demonstrated = [s.name for s in skills if s.status == "demonstrated"]
    related = [s.name for s in skills if s.status == "related"]
    missing = [s.name for s in skills if s.status == "not_demonstrated"]
    parts: list[str] = []
    if skills:
        line = f"You have {len(demonstrated)} of the {len(skills)} skills this job mentions"
        parts.append(line + (f" ({', '.join(demonstrated[:5])})." if demonstrated else "."))
    else:
        parts.append("No specific skills were detected in this posting.")
    if related:
        parts.append(f"Related experience: {', '.join(related[:4])}.")
    if missing:
        parts.append(f"Not shown on your resume: {', '.join(missing[:5])}.")
    parts.append(f"{experience_detail}. {location_detail}.")
    return " ".join(parts)
