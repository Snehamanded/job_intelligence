"""Rule-based tailoring: reorder by relevance to the job. No new wording, so nothing to verify."""

from app.schemas.tailoring import Change, ResumeDocument
from app.services.matching.skills import canonical, find_skills


def rule_changes(doc: ResumeDocument, job_skills: list[str]) -> list[Change]:
    wanted = {s: i for i, s in enumerate(job_skills)}
    changes: list[Change] = []

    def skill_rank(i_skill: tuple[int, str]) -> tuple[int, int]:
        i, name = i_skill
        position = wanted.get(canonical(name))
        return (0, position) if position is not None else (1, i)

    ordered = [
        doc.skills[i].id for i, _ in sorted(enumerate(s.name for s in doc.skills), key=skill_rank)
    ]
    if ordered != [s.id for s in doc.skills]:
        matched = [s.name for s in doc.skills if canonical(s.name) in wanted]
        changes.append(
            Change(
                id="rules-skills",
                kind="skills_order",
                source="rules",
                status="proposed",
                title="Put the skills this job asks for first",
                reason="Leads with " + ", ".join(matched[:5]) if matched else None,
                skill_ids=ordered,
                labels=[next(s.name for s in doc.skills if s.id == i) for i in ordered],
            )
        )

    for role in doc.experience:

        def hits(text: str) -> int:
            return len(set(find_skills(text)) & set(wanted))

        ordered_bullets = sorted(role.bullets, key=lambda b: -hits(b.original_text))
        if [b.id for b in ordered_bullets] != [b.id for b in role.bullets]:
            changes.append(
                Change(
                    id=f"rules-bullets-{role.id}",
                    kind="bullets_order",
                    source="rules",
                    status="proposed",
                    title=f"Lead with the most relevant bullets: {role.title}",
                    reason="Bullets mentioning this job's skills move up",
                    role_id=role.id,
                    bullet_ids=[b.id for b in ordered_bullets],
                    labels=[b.original_text for b in ordered_bullets],
                )
            )
    return changes
