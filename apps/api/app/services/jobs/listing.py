import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Application, Job, JobMatch
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import Preferences
from app.services.jobs.eligibility import Eligibility, evaluate
from app.services.matching.config import ScoringConfigService
from app.services.profile import preferences_of

Sort = Literal["rank", "newest"]


@dataclass
class ListedJob:
    job: Job
    eligibility: Eligibility
    match: JobMatch | None = None
    application: Application | None = None


@dataclass
class JobPage:
    items: list[ListedJob]
    total: int
    hidden_ineligible: int


class JobListingService:
    """Jobs with eligibility computed against the current profile version.

    Eligibility is cheap and deterministic, so it is computed on read. Match scores are stored
    per (profile version, scoring config version) and only current rows are shown.
    """

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def _context(self) -> tuple[Preferences, int | None]:
        profile = ProfileRepository(self._session).current(self._user_id)
        return preferences_of(profile), profile.experience_months if profile else None

    def current_matches(self, job_ids: list[uuid.UUID] | None = None) -> dict[uuid.UUID, JobMatch]:
        """Match rows for the current profile and scoring config versions only."""
        profile = ProfileRepository(self._session).current(self._user_id)
        if profile is None:
            return {}
        config_version, _ = ScoringConfigService(self._session, self._user_id).current()
        stmt = select(JobMatch).where(
            JobMatch.user_id == self._user_id,
            JobMatch.profile_version == profile.version,
            JobMatch.scoring_config_version == config_version,
        )
        if job_ids is not None:
            stmt = stmt.where(JobMatch.job_id.in_(job_ids))
        return {m.job_id: m for m in self._session.scalars(stmt)}

    def get(self, job_id: uuid.UUID) -> ListedJob | None:
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.user_id == self._user_id)
        )
        if job is None:
            return None
        prefs, months = self._context()
        match = self.current_matches([job.id]).get(job.id)
        return ListedJob(
            job, evaluate(job, prefs, months), match, self._applications([job.id]).get(job.id)
        )

    def _applications(self, job_ids: list[uuid.UUID] | None = None) -> dict[uuid.UUID, Application]:
        stmt = select(Application).where(
            Application.user_id == self._user_id, Application.job_id.is_not(None)
        )
        if job_ids is not None:
            stmt = stmt.where(Application.job_id.in_(job_ids))
        return {a.job_id: a for a in self._session.scalars(stmt) if a.job_id}

    def list(
        self,
        *,
        eligible_only: bool,
        high_priority_only: bool = False,
        sort: Sort = "rank",
        source: str | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> JobPage:
        stmt = select(Job).where(Job.user_id == self._user_id)
        if source:
            stmt = stmt.where(Job.source == source)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like)))
        stmt = stmt.order_by(Job.posted_at.desc().nulls_last(), Job.first_seen_at.desc())
        prefs, months = self._context()
        matches = self.current_matches()
        applications = self._applications()
        listed = [
            ListedJob(j, evaluate(j, prefs, months), matches.get(j.id), applications.get(j.id))
            for j in self._session.scalars(stmt)
        ]
        visible = [x for x in listed if x.eligibility.eligible] if eligible_only else listed
        if high_priority_only:
            visible = [x for x in visible if x.match and x.match.high_priority]
        if sort == "rank":
            # Scored jobs by rank; any not yet scored follow, newest first (stable sort).
            visible.sort(key=lambda x: -(x.match.rank_score if x.match else -1))
        return JobPage(
            items=visible[offset : offset + limit],
            total=len(visible),
            hidden_ineligible=len(listed) - len(visible),
        )

    def delete(self, job: Job) -> None:
        self._session.delete(job)
        self._session.commit()
