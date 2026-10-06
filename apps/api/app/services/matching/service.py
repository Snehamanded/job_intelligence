import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai.prompts import job_match as prompt
from app.ai.providers import AIProvider
from app.ai.schemas import JobMatchAssessment
from app.ai.services.embeddings import EmbeddingService, content_hash, cosine
from app.ai.services.runner import LLMRunner, LLMTask
from app.core.config import Settings
from app.models import CandidateProfile, Job, JobMatch
from app.repositories.profiles import ProfileRepository
from app.repositories.settings import SettingsRepository
from app.schemas.profile import ProfileData
from app.services.jobs.eligibility import Eligibility, evaluate
from app.services.matching import components as c
from app.services.matching.config import (
    COMPONENTS,
    ScoringConfigService,
    ScoringSettings,
    label_for,
)
from app.services.matching.explain import summary
from app.services.matching.refine import refine
from app.services.matching.skills import SkillMatch, classify, find_skills, skills_score
from app.services.profile import preferences_of

logger = logging.getLogger(__name__)

TASK = LLMTask(prompt.TASK, prompt.PROMPT_VERSION, prompt.SYSTEM_PROMPT, prompt.MAX_OUTPUT_TOKENS)
JOB_TEXT_CHARS = 6000
EMBED_TEXT_CHARS = 3000
_KEY_COLUMNS = {"id", "user_id", "job_id", "profile_version", "scoring_config_version"}


@dataclass
class MatchStats:
    scored: int
    llm_assessed: int
    method: str  # ai | embedding | lexical | skipped
    note: str | None = None


@dataclass
class _Draft:
    job: Job
    eligibility: Eligibility
    skills: list[SkillMatch]
    parts: dict[str, c.Component]
    similarity: float | None


def job_text(job: Job, limit: int = JOB_TEXT_CHARS) -> str:
    return f"{job.title}\n{job.company}\n{job.description_text[:limit]}"


def profile_payload(profile: CandidateProfile, data: ProfileData) -> dict[str, Any]:
    """Only verified facts go to the LLM."""
    return {
        "target_roles": profile.target_roles,
        "total_experience_months": profile.experience_months,
        "skills": [s.name for s in data.skills],
        "experience": [
            {
                "title": e.title,
                "company": e.company,
                "dates": e.date_text,
                "bullets": [b.text for b in e.bullets],
            }
            for e in data.experience
        ],
        "projects": [
            {"name": p.name, "description": p.description, "technologies": p.technologies}
            for p in data.projects
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree, "field": e.field_of_study}
            for e in data.education
        ],
    }


def profile_text(profile: CandidateProfile, data: ProfileData) -> str:
    return "\n".join(
        [
            "Target roles: " + ", ".join(profile.target_roles),
            "Roles: " + "; ".join(f"{e.title} at {e.company}" for e in data.experience),
            "Skills: " + ", ".join(s.name for s in data.skills),
            "Projects: " + "; ".join(f"{p.name} {p.description or ''}" for p in data.projects),
        ]
    )


class MatchingService:
    def __init__(
        self,
        session: Session,
        provider: AIProvider | None,
        settings: Settings,
        now: datetime | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._settings = settings
        self._now = now

    def rescore(self, user_id: uuid.UUID) -> MatchStats:
        profile = ProfileRepository(self._session).current(user_id)
        if profile is None:
            return MatchStats(0, 0, "skipped", "Upload a resume or set preferences to get scores")
        config_version, config = ScoringConfigService(self._session, user_id).current()
        user_settings = SettingsRepository(self._session).get_for_user(user_id)
        consent = bool(user_settings and user_settings.llm_consent)
        provider = self._provider if consent else None

        data = ProfileData.model_validate(profile.data)
        prefs = preferences_of(profile)
        pskills = c.profile_skill_map(data)
        jobs = list(self._session.scalars(select(Job).where(Job.user_id == user_id)))
        if not jobs:
            self._session.commit()
            return MatchStats(0, 0, "skipped", "No jobs to score yet")

        prepared = []
        for job in jobs:
            eligibility = evaluate(job, prefs, profile.experience_months)
            text = f"{job.title}\n{job.description_text}"
            skills = classify(find_skills(text, extra=list(pskills.values()))[:25], pskills)
            prepared.append((job, eligibility, skills))
        # Embed only what gets ranked (eligible jobs), best lexical skill fit first, capped per run.
        to_embed = sorted(
            (p for p in prepared if p[1].eligible),
            key=lambda p: skills_score(p[2]) or 0,
            reverse=True,
        )[: self._settings.embedding_max_jobs_per_run]
        sims = self._similarities(user_id, profile, data, [p[0] for p in to_embed], provider)

        drafts: list[_Draft] = []
        for job, eligibility, skills in prepared:
            sim = sims.get(job.id)
            scaled = (
                c.scale_similarity(
                    sim, self._settings.similarity_floor, self._settings.similarity_ceiling
                )
                if sim is not None
                else None
            )
            skill_score = skills_score(skills)
            role_part = c.role(job, prefs.target_roles, data, scaled)
            if skill_score is not None:
                skill_part = c.Component(
                    skill_score, "code", "Skills found in the posting vs your profile"
                )
            else:
                # No recognizable skills: don't reward vagueness. Use title fit, capped at neutral.
                skill_part = c.Component(
                    min(50, role_part.score),
                    "unknown",
                    "No specific skills listed in the posting; based on title fit",
                )
            drafts.append(
                _Draft(
                    job,
                    eligibility,
                    skills,
                    {
                        "skills": skill_part,
                        "experience": c.experience(job, profile.experience_months),
                        "role": role_part,
                        "location": c.location(eligibility),
                        "projects": c.projects_lexical([s.name for s in skills], data),
                        "industry": c.industry_unknown(),
                        "preferences": c.preferences(eligibility),
                    },
                    sim,
                )
            )

        assessed = self._assess_top(user_id, profile, data, pskills, drafts, config, consent)
        now = self._now or datetime.now(UTC)
        rows = [
            self._row(user_id, profile, config_version, config, d, assessed.get(d.job.id), now)
            for d in drafts
        ]
        stmt = insert(JobMatch).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_job_matches_key",
            set_={col: stmt.excluded[col] for col in rows[0] if col not in _KEY_COLUMNS}
            | {"updated_at": now},
        )
        self._session.execute(stmt)
        self._session.commit()
        method = "ai" if assessed else "embedding" if sims else "lexical"
        logger.info(
            "matches_scored",
            extra={
                "user_id": str(user_id),
                "jobs": len(rows),
                "llm_assessed": len(assessed),
                "method": method,
                "profile_version": profile.version,
                "scoring_config_version": config_version,
            },
        )
        return MatchStats(len(rows), len(assessed), method)

    def _similarities(
        self,
        user_id: uuid.UUID,
        profile: CandidateProfile,
        data: ProfileData,
        jobs: list[Job],
        provider: AIProvider | None,
    ) -> dict[uuid.UUID, float]:
        """Cosine similarity to the profile for jobs whose embedding is available."""
        if provider is None or not jobs:
            return {}
        service = EmbeddingService(self._session, provider, self._settings)
        profile_vecs = service.get_many(user_id, [profile_text(profile, data)], "profile")
        if not profile_vecs or profile_vecs[0] is None:
            return {}
        job_vecs = service.get_many(user_id, [job_text(j, EMBED_TEXT_CHARS) for j in jobs], "job")
        return {
            job.id: cosine(profile_vecs[0], vec)
            for job, vec in zip(jobs, job_vecs or [], strict=False)
            if vec is not None
        }

    def _match(self, parts: dict[str, c.Component], config: ScoringSettings) -> int:
        weights: dict[str, int] = config.weights.model_dump()
        total = sum(weights.values())
        return round(sum(parts[k].score * weights[k] for k in COMPONENTS) / total)

    def _assess_top(
        self,
        user_id: uuid.UUID,
        profile: CandidateProfile,
        data: ProfileData,
        pskills: dict[str, str],
        drafts: list[_Draft],
        config: ScoringSettings,
        consent: bool,
    ) -> dict[uuid.UUID, str]:
        """LLM refinement for the top N eligible jobs. Returns job id -> AI explanation."""
        if not consent or self._provider is None or config.llm_top_n == 0:
            return {}
        runner = LLMRunner(self._session, self._provider, self._settings)
        candidates = sorted(
            (d for d in drafts if d.eligibility.eligible),
            key=lambda d: (self._match(d.parts, config), d.similarity or 0),
            reverse=True,
        )[: config.llm_top_n]
        payload = profile_payload(profile, data)
        profile_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        explanations: dict[uuid.UUID, str] = {}
        for draft in candidates:
            job = draft.job
            job_skills = [s.name for s in draft.skills]
            posting = {
                "title": job.title,
                "company": job.company,
                "locations": job.locations,
                "description": job.description_text[:JOB_TEXT_CHARS],
            }
            outcome = runner.run(
                user_id,
                TASK,
                prompt=prompt.build_prompt(payload, posting, job_skills),
                schema=JobMatchAssessment,
                cache_key=content_hash(
                    f"{profile_hash}|{job.content_hash}|{json.dumps(job_skills)}"
                ),
                consent=True,
            )
            if outcome.value is None:
                if outcome.notice and "limit" in outcome.notice:
                    break  # over budget: stop asking
                continue
            refined = refine(outcome.value, draft.skills, pskills, data, job_text(job))
            draft.skills = refined.skills
            draft.parts["skills"] = c.Component(
                skills_score(refined.skills) or draft.parts["skills"].score,
                "ai",
                "Skills in the posting vs your profile, reviewed by AI",
            )
            draft.parts["projects"] = refined.projects
            draft.parts["industry"] = refined.industry
            explanations[job.id] = refined.explanation
        return explanations

    def _row(
        self,
        user_id: uuid.UUID,
        profile: CandidateProfile,
        config_version: int,
        config: ScoringSettings,
        draft: _Draft,
        ai_explanation: str | None,
        now: datetime,
    ) -> dict[str, Any]:
        job = draft.job
        weights = config.weights.model_dump()
        match = self._match(draft.parts, config)
        r = config.ranking
        rank = (
            r.match * match
            + r.freshness * 100 * c.freshness(job, now)
            + r.salary_fit * 100 * c.salary_fit(draft.eligibility, profile.min_salary is not None)
            + r.user_priority * 100 * (job.priority / 2)
        )
        methods = {p.method for p in draft.parts.values()}
        return {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "job_id": job.id,
            "profile_version": profile.version,
            "scoring_config_version": config_version,
            "match_score": match,
            "rank_score": round(rank, 2),
            "label": label_for(match, config.bands),
            "eligible": draft.eligibility.eligible,
            "high_priority": draft.eligibility.eligible and match >= config.high_priority_threshold,
            "components": {
                k: {"score": p.score, "weight": weights[k], "method": p.method, "detail": p.detail}
                for k, p in draft.parts.items()
            },
            "skills": [
                {"name": s.name, "status": s.status, "profile_skills": s.profile_skills}
                for s in draft.skills
            ],
            "explanation": ai_explanation
            or summary(
                draft.skills, draft.parts["experience"].detail, draft.parts["location"].detail
            ),
            "explanation_source": "ai" if ai_explanation else "summary",
            "method": "ai"
            if "ai" in methods
            else "embedding"
            if "embedding" in methods
            else "lexical",
            "similarity": draft.similarity,
        }
