import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Job
from app.services.jobs.normalize import NormalizedJob

Outcome = Literal["new", "updated", "duplicate"]


@dataclass
class StoreResult:
    job: Job
    outcome: Outcome


def _apply(job: Job, n: NormalizedJob) -> None:
    job.url = n.url
    job.title = n.title
    job.company = n.company
    job.locations = n.location.display
    job.cities = n.location.cities
    job.countries = n.location.countries
    job.remote_type = n.location.remote_type
    job.remote_regions = n.location.remote_regions
    job.employment_type = n.employment_type
    job.salary_min = n.salary.min if n.salary else None
    job.salary_max = n.salary.max if n.salary else None
    job.salary_currency = n.salary.currency if n.salary else None
    job.salary_period = n.salary.period if n.salary else None
    job.salary_text = n.salary.text if n.salary else None
    job.salary_unknown = n.salary is None
    job.experience_min_years = n.experience_min_years
    job.experience_max_years = n.experience_max_years
    job.description_text = n.description_text
    job.content_hash = n.content_hash
    job.dedupe_key = n.dedupe_key
    job.posted_at = n.posted_at
    job.is_mock = n.is_mock
    job.raw = n.raw


class JobStore:
    """Upserts normalized jobs for one user, collapsing duplicates.

    Order: the same source id updates in place; otherwise the same company/title/place key or
    the same description text means the job was already found on another source.
    """

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def save(self, n: NormalizedJob) -> StoreResult:
        now = datetime.now(UTC)
        existing = self._session.scalar(
            select(Job).where(
                Job.user_id == self._user_id,
                Job.source == n.source,
                Job.source_job_id == n.source_job_id,
            )
        )
        if existing is not None:
            _apply(existing, n)
            existing.last_seen_at = now
            self._session.flush()
            return StoreResult(existing, "updated")

        duplicate = self._session.scalar(
            select(Job)
            .where(
                Job.user_id == self._user_id,
                or_(Job.dedupe_key == n.dedupe_key, Job.content_hash == n.content_hash),
            )
            .order_by(Job.first_seen_at)
            .limit(1)
        )
        if duplicate is not None:
            seen = {(s["source"], s["source_job_id"]) for s in duplicate.also_seen_on}
            if (n.source, n.source_job_id) not in seen:
                duplicate.also_seen_on = [
                    *duplicate.also_seen_on,
                    {"source": n.source, "source_job_id": n.source_job_id, "url": n.url},
                ]
            duplicate.last_seen_at = now
            self._session.flush()
            return StoreResult(duplicate, "duplicate")

        job = Job(user_id=self._user_id, source=n.source, source_job_id=n.source_job_id,
                  first_seen_at=now, last_seen_at=now)  # fmt: skip
        _apply(job, n)
        self._session.add(job)
        self._session.flush()
        return StoreResult(job, "new")
