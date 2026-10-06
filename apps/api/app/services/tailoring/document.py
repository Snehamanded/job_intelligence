"""Builds the tailored document from a verified profile and applies accepted changes."""

from app.schemas.profile import ProfileData
from app.schemas.tailoring import (
    Change,
    DocBullet,
    DocCertification,
    DocEducation,
    DocProject,
    DocRole,
    DocSkill,
    ResumeDocument,
)


def base_document(data: ProfileData) -> ResumeDocument:
    """The resume as verified, with stable ids (skills s0.., roles r0.., bullets r0b0.., p0..)."""
    return ResumeDocument(
        contact=data.contact,
        skills=[
            DocSkill(id=f"s{i}", name=s.name, source_span=s.source_span)
            for i, s in enumerate(data.skills)
        ],
        experience=[
            DocRole(
                id=f"r{i}",
                title=e.title,
                company=e.company,
                location=e.location,
                date_text=e.date_text,
                source_span=e.source_span,
                bullets=[
                    DocBullet(
                        id=f"r{i}b{j}", text=b.text, original_text=b.text, source_span=b.source_span
                    )
                    for j, b in enumerate(e.bullets)
                ],
            )
            for i, e in enumerate(data.experience)
        ],
        projects=[
            DocProject(
                id=f"p{i}",
                name=p.name,
                description=p.description,
                technologies=p.technologies,
                source_span=p.source_span,
            )
            for i, p in enumerate(data.projects)
        ],
        education=[
            DocEducation(
                institution=e.institution,
                degree=e.degree,
                field_of_study=e.field_of_study,
                date_text=e.date_text,
                source_span=e.source_span,
            )
            for e in data.education
        ],
        certifications=[
            DocCertification(name=c.name, issuer=c.issuer, source_span=c.source_span)
            for c in data.certifications
        ],
    )


def item_texts(doc: ResumeDocument) -> dict[str, str]:
    """Id -> the verified text of each citable item."""
    texts: dict[str, str] = {s.id: s.name for s in doc.skills}
    for role in doc.experience:
        texts[role.id] = f"{role.title} at {role.company} {role.date_text or ''}".strip()
        for b in role.bullets:
            texts[b.id] = b.original_text
    for p in doc.projects:
        texts[p.id] = " ".join([p.name, p.description or "", ", ".join(p.technologies)])
    return texts


def role_text(role: DocRole) -> str:
    return "\n".join([role.title, role.company, *(b.original_text for b in role.bullets)])


def apply(base: ResumeDocument, changes: list[Change]) -> ResumeDocument:
    """Apply accepted, supported changes. Unsupported changes are never applied."""
    doc = base.model_copy(deep=True)
    accepted = [c for c in changes if c.decision == "accepted" and c.status == "proposed"]
    for change in accepted:
        if change.kind == "skills_order" and change.skill_ids is not None:
            skills_by_id = {s.id: s for s in doc.skills}
            doc.skills = [skills_by_id[i] for i in change.skill_ids if i in skills_by_id]
        elif change.kind == "bullets_order" and change.bullet_ids is not None:
            for role in doc.experience:
                if role.id == change.role_id:
                    bullets_by_id = {b.id: b for b in role.bullets}
                    role.bullets = [
                        bullets_by_id[i] for i in change.bullet_ids if i in bullets_by_id
                    ]
    for change in accepted:  # rewrites after reordering, so they find their bullet anywhere
        if change.kind == "bullet_rewrite" and change.after:
            for role in doc.experience:
                for bullet in role.bullets:
                    if bullet.id == change.bullet_id:
                        bullet.text, bullet.ai_changed = change.after, True
        elif change.kind == "summary" and change.sentences:
            doc.summary = list(change.sentences)
    return doc
