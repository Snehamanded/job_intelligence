"""Global remote-job feeds: Remote OK and Remotive (Tier A).

Both require a link back and naming them as the source, and ask for modest request rates.
Verified 2026-10-06: see docs/SOURCE_FEASIBILITY.md.
"""

from collections.abc import Iterator
from typing import Any

import httpx

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.common import employment, https_or_none, parse_time, structured_salary
from app.connectors.http import get_json
from app.services.jobs.normalize import RawPosting
from app.utils.html_text import html_to_text
from app.utils.salary import parse_salary


class RemoteOKConnector:
    name = "remoteok"
    label = "Remote OK"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True  # enabled per user
    URL = "https://remoteok.com/api"

    def __init__(
        self, client: httpx.Client, *, min_interval_seconds: int = 3600, max_jobs: int = 1000
    ):
        self._client = client
        self.min_interval_seconds = min_interval_seconds
        self._max_jobs = max_jobs

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        data = get_json(self._client, self.URL, self.label)
        if not isinstance(data, list):
            raise ConnectorError("Remote OK returned an unexpected response")
        # The first element is the API's legal notice, not a job.
        for job in [j for j in data if isinstance(j, dict) and "position" in j][: self._max_jobs]:
            yield to_remoteok(job)


def to_remoteok(job: dict[str, Any]) -> RawPosting:
    location = str(job.get("location") or "").strip()
    salary = structured_salary(job.get("salary_min"), job.get("salary_max"), "USD", "year",
                               "Salary as listed on Remote OK (USD per year)")  # fmt: skip
    return RawPosting(
        source="remoteok",
        source_job_id=str(job.get("id")),
        title=str(job.get("position") or "Untitled role").strip(),
        company=str(job.get("company") or "Unknown company").strip(),
        location_text=f"Remote, {location}" if location else "Remote",
        description_text=html_to_text(str(job.get("description") or "")),
        url=https_or_none(job.get("url")),
        posted_at=parse_time(job.get("date")) or parse_time(job.get("epoch")),
        salary=salary,
        raw={k: v for k, v in job.items() if k not in ("description", "logo", "company_logo")},
    )


class RemotiveConnector:
    name = "remotive"
    label = "Remotive"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True
    URL = "https://remotive.com/api/remote-jobs"

    def __init__(
        self, client: httpx.Client, *, min_interval_seconds: int = 6 * 3600, max_jobs: int = 1000
    ):
        self._client = client
        self.min_interval_seconds = min_interval_seconds
        self._max_jobs = max_jobs

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        # One request for everything; filtering happens locally (Remotive asks for few requests).
        data = get_json(self._client, self.URL, self.label)
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise ConnectorError("Remotive returned an unexpected response")
        for job in [j for j in jobs if isinstance(j, dict) and "id" in j][: self._max_jobs]:
            yield to_remotive(job)


def to_remotive(job: dict[str, Any]) -> RawPosting:
    region = str(job.get("candidate_required_location") or "").strip()
    salary_text = str(job.get("salary") or "").strip()
    return RawPosting(
        source="remotive",
        source_job_id=str(job["id"]),
        title=str(job.get("title") or "Untitled role").strip(),
        company=str(job.get("company_name") or "Unknown company").strip(),
        location_text="; ".join(f"Remote, {r.strip()}" for r in region.split(",") if r.strip())
        or "Remote",
        description_text=html_to_text(str(job.get("description") or "")),
        url=https_or_none(job.get("url")),
        posted_at=parse_time(job.get("publication_date")),
        salary=parse_salary(f"Salary: {salary_text}") if salary_text else None,
        employment_hint=employment(job.get("job_type")),
        raw={
            k: v
            for k, v in job.items()
            if k not in ("description", "company_logo", "company_logo_url")
        },
    )
