"""Template letter built in code, used without AI. Every factual sentence cites its source."""

import re

from app.schemas.cover_letters import Paragraph, Sentence, SentenceKind
from app.schemas.tailoring import ResumeDocument
from app.services.matching.skills import canonical, find_skills


def _first_person(bullet: str) -> str:
    text = bullet.strip().rstrip(".")
    return text[0].lower() + text[1:] if text and not re.match(r"[A-Z]{2}", text) else text


def build_template(
    doc: ResumeDocument, job_title: str, company: str, job_skills: list[str], length: str
) -> tuple[list[Paragraph], str | None]:
    wanted = set(job_skills)
    n_bullets = 2 if length == "short" else 3

    def relevance(text: str) -> int:
        return len(set(find_skills(text)) & wanted)

    ranked = sorted(
        ((role, b) for role in doc.experience for b in role.bullets),
        key=lambda rb: -relevance(rb[1].original_text),
    )[:n_bullets]

    def s(i: str, text: str, kind: SentenceKind, sources: list[str] | None = None) -> Sentence:
        return Sentence(
            id=i, text=text, kind=kind, sources=sources or [], source="template", status="proposed"
        )

    opening = [
        s("t0", f"I'm writing to apply for the {job_title} role at {company}.", "connective")
    ]
    body = [
        s(
            f"t{1 + i}",
            f"As {role.title} at {role.company}, I {_first_person(b.original_text)}.",
            "claim",
            [b.id, role.id],
        )
        for i, (role, b) in enumerate(ranked)
    ]
    order = {name: i for i, name in enumerate(job_skills)}
    # In the order the job lists them, so the letter mirrors what the posting asks for first.
    matched = sorted(
        (sk for sk in doc.skills if canonical(sk.name) in wanted),
        key=lambda sk: order[canonical(sk.name)],
    )[:5]
    if matched:
        names = [sk.name for sk in matched]
        listed = ", ".join(names[:-1]) + (f" and {names[-1]}" if len(names) > 1 else names[0])
        body.append(
            s(
                "t9",
                f"My skills include {listed}, which this role asks for.",
                "claim",
                [sk.id for sk in matched],
            )
        )
    closing = [
        s(
            "t10",
            "I would welcome the chance to discuss how I can contribute to your team.",
            "connective",
        ),
        s("t11", "Thank you for your time and consideration.", "connective"),
    ]
    paragraphs = [
        Paragraph(id="p0", sentences=opening),
        Paragraph(id="p1", sentences=body),
        Paragraph(id="p2", sentences=closing),
    ]
    return paragraphs, doc.contact.name
