import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.prompts import tailor_resume as prompt
from app.ai.providers import AIProvider
from app.ai.schemas import TailorSuggestions, VerifyReport
from app.ai.services.runner import LLMRunner, LLMTask
from app.core.config import Settings
from app.models import CandidateProfile, Job, ResumeVersion
from app.repositories.profiles import ProfileRepository
from app.repositories.settings import SettingsRepository
from app.schemas.profile import ProfileData
from app.schemas.tailoring import (
    Change,
    ResumeDocument,
    SkillGap,
    SummarySentence,
)
from app.services.jobs.listing import JobListingService
from app.services.matching.components import profile_skill_map
from app.services.matching.skills import classify, find_skills
from app.services.tailoring.checks import check_rewrite, check_summary_sentence
from app.services.tailoring.document import apply, base_document, item_texts, role_text
from app.services.tailoring.rules import rule_changes

logger = logging.getLogger(__name__)

SUGGEST = LLMTask(
    prompt.TASK, prompt.PROMPT_VERSION, prompt.SYSTEM_PROMPT, prompt.MAX_OUTPUT_TOKENS
)
VERIFY = LLMTask(
    prompt.VERIFY_TASK,
    prompt.VERIFY_PROMPT_VERSION,
    prompt.VERIFY_SYSTEM_PROMPT,
    prompt.VERIFY_MAX_OUTPUT_TOKENS,
)
UNVERIFIED = "Couldn't be checked by the second validation pass. Try generating again."
NO_AI_NOTICE = "AI processing is off, so only rule-based changes are suggested (no rewording)."


class TailoringError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def _ai_items(doc: ResumeDocument) -> dict[str, Any]:
    return {
        "skills": [{"id": s.id, "name": s.name} for s in doc.skills],
        "roles": [
            {
                "id": r.id,
                "title": r.title,
                "company": r.company,
                "dates": r.date_text,
                "bullets": [{"id": b.id, "text": b.original_text} for b in r.bullets],
            }
            for r in doc.experience
        ],
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "technologies": p.technologies,
            }
            for p in doc.projects
        ],
    }


class TailoringService:
    def __init__(
        self, session: Session, user_id: uuid.UUID, provider: AIProvider | None, settings: Settings
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._provider = provider
        self._settings = settings

    # --- lookups -------------------------------------------------------------------------

    def get(self, version_id: uuid.UUID) -> ResumeVersion | None:
        return self._session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id, ResumeVersion.user_id == self._user_id
            )
        )

    def all(self, job_id: uuid.UUID | None = None) -> list[ResumeVersion]:
        stmt = select(ResumeVersion).where(ResumeVersion.user_id == self._user_id)
        if job_id:
            stmt = stmt.where(ResumeVersion.job_id == job_id)
        return list(self._session.scalars(stmt.order_by(ResumeVersion.created_at.desc())))

    def _profile(self, version: int) -> CandidateProfile | None:
        return self._session.scalar(
            select(CandidateProfile).where(
                CandidateProfile.user_id == self._user_id, CandidateProfile.version == version
            )
        )

    def _job(self, job_id: uuid.UUID | None) -> Job | None:
        if job_id is None:
            return None
        return self._session.scalar(
            select(Job).where(Job.id == job_id, Job.user_id == self._user_id)
        )

    def base(self, version: ResumeVersion) -> ResumeDocument:
        profile = self._profile(version.profile_version)
        data = ProfileData.model_validate(profile.data) if profile else ProfileData()
        return base_document(data)

    # --- create and generate -------------------------------------------------------------

    def create(self, job_id: uuid.UUID) -> ResumeVersion:
        job = self._job(job_id)
        if job is None:
            raise TailoringError("Job not found", 404)
        profile = ProfileRepository(self._session).current(self._user_id)
        if profile is None or not ProfileData.model_validate(profile.data).experience:
            raise TailoringError("Upload your resume first, so there is something to tailor.")
        latest = self._session.scalar(
            select(func.max(ResumeVersion.version)).where(ResumeVersion.user_id == self._user_id)
        )
        version = ResumeVersion(
            user_id=self._user_id,
            version=(latest or 0) + 1,
            profile_version=profile.version,
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            name=f"{job.title} at {job.company}"[:200],
            status="generating",
            method="rules",
            changes=[],
        )
        self._session.add(version)
        self._session.commit()
        return version

    def generate(self, version_id: uuid.UUID) -> None:
        version = self.get(version_id)
        if version is None or version.status != "generating":
            return
        job = self._job(version.job_id)
        if job is None:
            version.status, version.notice = "failed", "The job was removed."
            self._session.commit()
            return
        base = self.base(version)
        job_skills = find_skills(f"{job.title}\n{job.description_text}")
        changes = rule_changes(base, job_skills)

        settings_row = SettingsRepository(self._session).get_for_user(self._user_id)
        consent = bool(settings_row and settings_row.llm_consent)
        notice: str | None = NO_AI_NOTICE if not consent or self._provider is None else None
        if notice is None:
            ai_changes, notice = self._ai_changes(base, job)
            changes += ai_changes
            if ai_changes:
                version.method = "ai"
        version.changes = [c.model_dump(mode="json") for c in changes]
        version.status, version.notice = "ready", notice
        self._session.commit()
        logger.info(
            "tailoring_generated",
            extra={
                "version_id": str(version.id),
                "method": version.method,
                "changes": len(changes),
                "unsupported": sum(c.status == "unsupported" for c in changes),
            },
        )

    def _ai_changes(self, base: ResumeDocument, job: Job) -> tuple[list[Change], str | None]:
        runner = LLMRunner(self._session, self._provider, self._settings)
        items = _ai_items(base)
        posting = {
            "title": job.title,
            "company": job.company,
            "description": job.description_text[:6000],
        }
        key = hashlib.sha256(
            json.dumps([items, job.content_hash], sort_keys=True).encode()
        ).hexdigest()
        outcome = runner.run(
            self._user_id,
            SUGGEST,
            prompt=prompt.build_prompt(items, posting),
            schema=TailorSuggestions,
            cache_key=key,
            consent=True,
        )
        if outcome.value is None:
            return [], f"{outcome.notice} Only rule-based changes are suggested."
        changes = self._convert(base, outcome.value)
        self._verify(runner, base, changes, key)
        return changes, None

    def _convert(self, base: ResumeDocument, s: TailorSuggestions) -> list[Change]:
        """Turn suggestions into changes, dropping invalid references and running code checks."""
        changes: list[Change] = []
        skill_ids = {sk.id for sk in base.skills}
        order = [i for i in dict.fromkeys(s.skills_order) if i in skill_ids]
        if order and order != [sk.id for sk in base.skills]:
            changes.append(
                Change(
                    id="ai-skills",
                    kind="skills_order",
                    source="ai",
                    status="proposed",
                    title="Reorder skills for this job",
                    skill_ids=order,
                    labels=[next(sk.name for sk in base.skills if sk.id == i) for i in order],
                )
            )
        roles = {r.id: r for r in base.experience}
        for ro in s.roles:
            role = roles.get(ro.role_id)
            if role is None:
                continue
            valid = {b.id for b in role.bullets}
            ids = [i for i in dict.fromkeys(ro.bullet_ids) if i in valid]
            if ids and ids != [b.id for b in role.bullets]:
                changes.append(
                    Change(
                        id=f"ai-bullets-{role.id}",
                        kind="bullets_order",
                        source="ai",
                        status="proposed",
                        title=f"Reorder bullets: {role.title}",
                        role_id=role.id,
                        bullet_ids=ids,
                        labels=[
                            next(b.original_text for b in role.bullets if b.id == i) for i in ids
                        ],
                    )
                )
        bullets = {b.id: (r, b) for r in base.experience for b in r.bullets}
        seen: set[str] = set()
        for rw in s.rewrites:
            if rw.bullet_id not in bullets or rw.bullet_id in seen:
                continue
            seen.add(rw.bullet_id)
            role, bullet = bullets[rw.bullet_id]
            after = " ".join(rw.text.split())
            if after == bullet.original_text:
                continue
            issues = check_rewrite(bullet.original_text, after, role_text(role))
            changes.append(
                Change(
                    id=f"ai-rewrite-{bullet.id}",
                    kind="bullet_rewrite",
                    source="ai",
                    status="unsupported" if issues else "proposed",
                    title=f"Reword a bullet: {role.title}",
                    reason=rw.reason or None,
                    issues=issues,
                    role_id=role.id,
                    bullet_id=bullet.id,
                    before=bullet.original_text,
                    after=after,
                )
            )
        if s.summary:
            texts = item_texts(base)
            sentences = [
                SummarySentence(text=" ".join(x.text.split()), sources=x.sources) for x in s.summary
            ]
            issues = [
                i for x in sentences for i in check_summary_sentence(x.text, x.sources, texts)
            ]
            changes.append(
                Change(
                    id="ai-summary",
                    kind="summary",
                    source="ai",
                    status="unsupported" if issues else "proposed",
                    title="Add a short summary",
                    issues=issues,
                    sentences=sentences,
                )
            )
        return changes

    def _verify(
        self, runner: LLMRunner, base: ResumeDocument, changes: list[Change], key: str
    ) -> None:
        """Second pass: an independent check of every new wording that passed the code checks."""
        texts = item_texts(base)
        to_check = [
            c for c in changes if c.kind in ("bullet_rewrite", "summary") and c.status == "proposed"
        ]
        if not to_check:
            return
        payload = []
        for c in to_check:
            if c.kind == "bullet_rewrite":
                payload.append(
                    {"change_id": c.id, "original": c.before or "", "rewrite": c.after or ""}
                )
            else:
                cited = sorted({s for x in c.sentences or [] for s in x.sources if s in texts})
                payload.append(
                    {
                        "change_id": c.id,
                        "original": "\n".join(texts[s] for s in cited),
                        "rewrite": " ".join(x.text for x in c.sentences or []),
                    }
                )
        outcome = runner.run(
            self._user_id,
            VERIFY,
            prompt=prompt.build_verify_prompt(payload),
            schema=VerifyReport,
            cache_key=hashlib.sha256(json.dumps([key, payload]).encode()).hexdigest(),
            consent=True,
        )
        results = {r.change_id: r for r in outcome.value.results} if outcome.value else {}
        for c in to_check:
            r = results.get(c.id)
            if r is None:
                c.status, c.issues = "unsupported", [UNVERIFIED]
            elif not r.supported:
                c.status = "unsupported"
                c.issues = [f"Second check: {p}" for p in r.problems] or [
                    "Second check: not supported"
                ]

    # --- review and save -----------------------------------------------------------------

    def changes(self, version: ResumeVersion) -> list[Change]:
        return [Change.model_validate(c) for c in version.changes]

    def decide(self, version: ResumeVersion, decisions: dict[str, str]) -> ResumeVersion:
        if version.status != "ready":
            raise TailoringError("Only a version under review can be changed.", 409)
        changes = {c.id: c for c in self.changes(version)}
        for change_id, decision in decisions.items():
            change = changes.get(change_id)
            if change is None:
                raise TailoringError(f"Unknown change: {change_id}")
            if decision == "accepted" and change.status == "unsupported":
                raise TailoringError(
                    "Unsupported changes can't be accepted: " + "; ".join(change.issues)
                )
            change.decision = decision  # type: ignore[assignment]
            if decision == "accepted":
                # One accepted change per target: accepting replaces any alternative.
                for other in changes.values():
                    if (
                        other.id != change.id
                        and other.kind == change.kind
                        and (
                            other.role_id == change.role_id and other.bullet_id == change.bullet_id
                        )
                        and other.decision == "accepted"
                    ):
                        other.decision = "rejected"
        version.changes = [c.model_dump(mode="json") for c in changes.values()]
        self._session.commit()
        return version

    def preview(self, version: ResumeVersion) -> ResumeDocument:
        if version.status == "saved" and version.content:
            return ResumeDocument.model_validate(version.content)
        return apply(self.base(version), self.changes(version))

    def save(self, version: ResumeVersion, name: str | None) -> ResumeVersion:
        if version.status != "ready":
            raise TailoringError("Only a version under review can be saved.", 409)
        base = self.base(version)
        changes = self.changes(version)
        # Defense in depth: re-run the code checks on everything being applied.
        roles = {r.id: r for r in base.experience}
        texts = item_texts(base)
        for c in changes:
            if c.decision != "accepted":
                continue
            if c.kind == "bullet_rewrite":
                role = roles.get(c.role_id or "")
                if role is None or check_rewrite(c.before or "", c.after or "", role_text(role)):
                    raise TailoringError("An accepted rewrite no longer passes the checks.")
            if c.kind == "summary" and any(
                check_summary_sentence(s.text, s.sources, texts) for s in c.sentences or []
            ):
                raise TailoringError("The accepted summary no longer passes the checks.")
        version.content = apply(base, changes).model_dump(mode="json")
        version.status = "saved"
        if name and name.strip():
            version.name = name.strip()[:200]
        self._session.commit()
        logger.info(
            "tailoring_saved",
            extra={
                "version_id": str(version.id),
                "accepted": sum(c.decision == "accepted" for c in changes),
            },
        )
        return version

    def delete(self, version: ResumeVersion) -> None:
        self._session.delete(version)
        self._session.commit()

    def skill_gaps(self, version: ResumeVersion) -> list[SkillGap]:
        """Job skills not on the resume. Shown beside the editor, never in the resume."""
        job = self._job(version.job_id)
        if job is None:
            return []
        match = (
            JobListingService(self._session, self._user_id).current_matches([job.id]).get(job.id)
        )
        if match:
            skills = [s for s in match.skills if s["status"] != "demonstrated"]
            return [
                SkillGap(name=s["name"], status=s["status"], profile_skills=s["profile_skills"])
                for s in skills
            ]
        profile = self._profile(version.profile_version)
        data = ProfileData.model_validate(profile.data) if profile else ProfileData()
        found = classify(
            find_skills(f"{job.title}\n{job.description_text}"), profile_skill_map(data)
        )
        return [
            SkillGap(name=m.name, status=m.status, profile_skills=m.profile_skills)
            for m in found
            if m.status != "demonstrated"
        ]
