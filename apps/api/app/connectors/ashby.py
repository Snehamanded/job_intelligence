"""Ashby public job posting API (Tier A). Verified 2026-10-06: see docs/SOURCE_FEASIBILITY.md."""

import re
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.common import SLUG_RE, employment, parse_time, structured_salary
from app.connectors.http import get_json
from app.services.jobs.normalize import RawPosting
from app.utils.salary import Period, Salary

API = "https://api.ashbyhq.com/posting-api/job-board"
JOB_URL_RE = re.compile(
    r"^https://jobs\.ashbyhq\.com/(?P<board>[A-Za-z0-9_.-]+)/(?P<id>[0-9a-f-]{36})"
)
_INTERVALS: dict[str, Period] = {"1 YEAR": "year", "1 MONTH": "month", "1 HOUR": "hour"}


def parse_job_url(url: str) -> tuple[str, str] | None:
    m = JOB_URL_RE.match(url.strip())
    return (m.group("board"), m.group("id")) if m else None


def _salary(job: dict[str, Any]) -> Salary | None:
    # Only what the employer chose to show on the posting.
    if not job.get("shouldDisplayCompensationOnJobPostings"):
        return None
    comp = job.get("compensation") or {}
    for c in comp.get("summaryComponents") or []:
        if c.get("compensationType") == "Salary" and c.get("interval") in _INTERVALS:
            return structured_salary(
                c.get("minValue"), c.get("maxValue"), c.get("currencyCode"),
                _INTERVALS[c["interval"]], comp.get("compensationTierSummary"),
            )  # fmt: skip
    return None


def to_posting(job: dict[str, Any], board: str, company: str) -> RawPosting:
    primary = str(job.get("location") or "")
    workplace = (job.get("workplaceType") or "").lower()
    if not workplace and job.get("isRemote"):
        workplace = "remote"
    # The primary location follows workplaceType; secondary ones carry their own wording,
    # e.g. "Remote (Canada)".
    if primary and workplace == "remote":
        primary = f"Remote, {primary}"
    elif primary and workplace == "hybrid":
        primary = f"Hybrid - {primary}"
    secondary = [
        str(s.get("location")) for s in job.get("secondaryLocations") or []
        if isinstance(s, dict) and s.get("location")
    ]  # fmt: skip
    location = "; ".join(x for x in [primary, *secondary] if x) or (
        "Remote" if workplace == "remote" else ""
    )
    return RawPosting(
        source="ashby",
        source_job_id=f"{board}:{job['id']}",
        title=str(job.get("title") or "Untitled role"),
        company=company,
        location_text=location,
        description_text=str(job.get("descriptionPlain") or ""),
        url=job.get("jobUrl") if str(job.get("jobUrl", "")).startswith("https://") else None,
        posted_at=parse_time(job.get("publishedAt")),
        salary=_salary(job),
        employment_hint=employment(job.get("employmentType")),
        raw={k: v for k, v in job.items() if k not in ("descriptionHtml", "descriptionPlain")},
    )


class AshbyConnector:
    name = "ashby"
    label = "Ashby"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True
    min_interval_seconds = 0

    def __init__(
        self,
        client: httpx.Client,
        *,
        delay_seconds: float = 1.0,
        max_jobs: int = 1000,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._delay = delay_seconds
        self._max_jobs = max_jobs
        self._sleep = sleep

    def _board(self, board: str) -> list[dict[str, Any]]:
        data = get_json(self._client, f"{API}/{board}", "Ashby", {"includeCompensation": "true"})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise ConnectorError("Ashby returned an unexpected response")
        return [j for j in jobs if isinstance(j, dict) and "id" in j and j.get("isListed", True)]

    def validate(self, board: str) -> str:
        if not SLUG_RE.fullmatch(board):
            raise ConnectorError("Use the board name from its jobs.ashbyhq.com link")
        self._board(board)
        return board.replace("-", " ").title()

    def fetch_job(self, board: str, job_id: str, company: str) -> RawPosting:
        job = next((j for j in self._board(board) if j["id"] == job_id), None)
        if job is None:
            raise ConnectorError("This job is no longer listed")
        return to_posting(job, board, company)

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        boards = [t for t in query.targets if SLUG_RE.fullmatch(t.split("|")[0])]
        if not boards:
            raise ConnectorError("No Ashby boards configured")
        yielded = failures = 0
        for i, target in enumerate(boards):
            board, _, company = target.partition("|")
            if i:
                self._sleep(self._delay)
            try:
                jobs = self._board(board)
            except ConnectorError as exc:
                failures += 1
                report.errors.append(f"{board}: {exc}")
                continue
            for job in jobs:
                if yielded >= self._max_jobs:
                    return
                yielded += 1
                yield to_posting(job, board, company or board.title())
        if failures == len(boards):
            raise ConnectorError("; ".join(report.errors))
