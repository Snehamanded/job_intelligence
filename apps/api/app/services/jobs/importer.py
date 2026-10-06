import hashlib
import uuid

from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.greenhouse import GreenhouseConnector, parse_job_url
from app.models import Job
from app.services.jobs.normalize import RawPosting, normalize
from app.services.jobs.store import JobStore


class ImportRejectedError(Exception):
    """The import can't be done. The message is safe to show the user."""


class JobImporter:
    def __init__(
        self, session: Session, user_id: uuid.UUID, greenhouse: GreenhouseConnector
    ) -> None:
        self._session = session
        self._store = JobStore(session, user_id)
        self._greenhouse = greenhouse

    def from_url(self, url: str) -> Job:
        parsed = parse_job_url(url)
        if parsed is None:
            raise ImportRejectedError(
                "Only Greenhouse job links can be imported automatically for now. "
                "Paste the job description instead."
            )
        try:
            posting = self._greenhouse.fetch_job(*parsed)
        except ConnectorError as exc:
            raise ImportRejectedError(f"Could not import this job: {exc}") from exc
        return self._save(posting)

    def from_text(
        self, *, title: str, company: str, location: str, description: str, url: str | None
    ) -> Job:
        digest = hashlib.sha256(f"{title}|{company}|{description}".encode()).hexdigest()[:32]
        posting = RawPosting(
            source="manual",
            source_job_id=digest,
            title=title,
            company=company,
            location_text=location,
            description_text=description.strip(),
            url=url if url and url.startswith(("https://", "http://")) else None,
        )
        return self._save(posting)

    def _save(self, posting: RawPosting) -> Job:
        job = self._store.save(normalize(posting)).job
        self._session.commit()
        return job
