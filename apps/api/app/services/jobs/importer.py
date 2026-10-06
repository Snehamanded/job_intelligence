import hashlib
import uuid
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.connectors import ashby, greenhouse, jsonld, lever
from app.connectors.base import ConnectorError
from app.connectors.registry import Connectors
from app.connectors.safe_http import UnsafeURLError
from app.models import Job
from app.services.jobs.normalize import RawPosting, normalize
from app.services.jobs.store import JobStore

# Tier C sites (docs/SOURCE_FEASIBILITY.md): their terms restrict automated access, so their pages
# are never fetched, whatever robots.txt says. The user pastes the description instead.
NO_FETCH_DOMAINS = {
    "linkedin.com": "LinkedIn", "naukri.com": "Naukri", "indeed.com": "Indeed",
    "indeed.co.in": "Indeed", "glassdoor.com": "Glassdoor", "glassdoor.co.in": "Glassdoor",
    "foundit.in": "Foundit", "shine.com": "Shine", "apna.co": "Apna", "wellfound.com": "Wellfound",
    "instahyre.com": "Instahyre", "cutshort.io": "Cutshort", "hirist.tech": "Hirist",
    "hirist.com": "Hirist", "ziprecruiter.com": "ZipRecruiter",
    "google.com": "Google", "api.smartrecruiters.com": "SmartRecruiters' API",
}  # fmt: skip


# Career-portal platforms recognized from the page's host, to label imported jobs.
PLATFORM_HOSTS = {
    "myworkdayjobs.com": "workday", "myworkdaysite.com": "workday",
    "smartrecruiters.com": "smartrecruiters", "icims.com": "icims", "taleo.net": "taleo",
    "successfactors.com": "successfactors", "successfactors.eu": "successfactors",
}  # fmt: skip


def platform_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    for domain, platform in PLATFORM_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return "careers"


def restricted_site(url: str) -> str | None:
    host = (urlsplit(url.strip()).hostname or "").lower()
    for domain, label in NO_FETCH_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return label
    return None


class ImportRejectedError(Exception):
    """The import can't be done. The message is safe to show the user."""


class JobImporter:
    def __init__(self, session: Session, user_id: uuid.UUID, connectors: Connectors) -> None:
        self._session = session
        self._store = JobStore(session, user_id)
        self._connectors = connectors

    def from_url(self, url: str) -> Job:
        """ATS links go through their APIs; any other page through its JobPosting data."""
        if site := restricted_site(url):
            raise ImportRejectedError(
                f"{site} doesn't allow automated access, so its pages aren't fetched. "
                "Paste the job description instead."
            )
        try:
            if gh := greenhouse.parse_job_url(url):
                posting = self._connectors.greenhouse.fetch_job(*gh)
            elif lv := lever.parse_job_url(url):
                region, site, posting_id = lv
                posting = self._connectors.lever.fetch_job(region, site, posting_id, site.title())
            elif ab := ashby.parse_job_url(url):
                board, job_id = ab
                posting = self._connectors.ashby.fetch_job(board, job_id, board.title())
            else:
                posting = self._from_career_page(url)
        except (ConnectorError, UnsafeURLError) as exc:
            raise ImportRejectedError(f"Could not import this job: {exc}") from exc
        return self._save(posting)

    def _from_career_page(self, url: str) -> RawPosting:
        final_url, html = self._connectors.fetcher.fetch_page(url, refuse=restricted_site)
        jobs = jsonld.find_job_postings(html)
        if not jobs:
            raise ImportRejectedError(
                "This page doesn't publish job details in a standard format. "
                "Paste the job description instead."
            )
        posting = jsonld.to_posting(jobs[0], final_url)
        posting.source = platform_of(final_url)
        return posting

    def from_text(
        self, *, title: str, company: str, location: str, description: str, url: str | None
    ) -> Job:
        key = f"{title}|{company}|{location}|{description}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
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
