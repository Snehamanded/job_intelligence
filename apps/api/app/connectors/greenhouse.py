"""Greenhouse Job Board API (Tier A). Verified 2026-10-05: see docs/CONNECTORS.md."""

import logging
import re
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import httpx

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.services.jobs.normalize import RawPosting
from app.utils.html_text import html_to_text
from app.utils.salary import Salary

logger = logging.getLogger(__name__)

API = "https://boards-api.greenhouse.io/v1/boards"
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
JOB_URL_RE = re.compile(
    r"^https://(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?P<token>[A-Za-z0-9_-]+)/jobs/(?P<id>\d+)"
)


def valid_token(token: str) -> bool:
    return bool(TOKEN_RE.fullmatch(token))


def parse_job_url(url: str) -> tuple[str, str] | None:
    """(board_token, job_id) from a public Greenhouse job URL."""
    m = JOB_URL_RE.match(url.strip())
    return (m.group("token").lower(), m.group("id")) if m else None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _pay(job: dict[str, Any]) -> Salary | None:
    """Structured pay ranges, when the employer publishes them (amounts are in cents)."""
    for r in job.get("pay_input_ranges") or []:
        try:
            low = int(r["min_cents"]) // 100
            high = int(r["max_cents"]) // 100
            currency = str(r["currency_type"]).upper()[:3]
        except (KeyError, TypeError, ValueError):
            continue
        if low > 0 and high >= low and len(currency) == 3:
            return Salary(min=low, max=high, currency=currency, period="year",
                          text=f"{currency} {low:,} – {high:,}")  # fmt: skip
    return None


def to_posting(job: dict[str, Any], token: str, company: str) -> RawPosting:
    location = (job.get("location") or {}).get("name") or ""
    offices = [o.get("location") or o.get("name") for o in job.get("offices") or []]
    if not location and offices:
        location = "; ".join(o for o in offices if o)
    return RawPosting(
        source="greenhouse",
        source_job_id=f"{token}:{job['id']}",
        title=str(job.get("title") or "Untitled role"),
        company=str(job.get("company_name") or company),
        location_text=str(location),
        description_text=html_to_text(str(job.get("content") or ""), double_escaped=True),
        url=job.get("absolute_url")
        if str(job.get("absolute_url", "")).startswith("https://")
        else None,
        posted_at=_datetime(job.get("first_published")) or _datetime(job.get("updated_at")),
        salary=_pay(job),
        raw={k: v for k, v in job.items() if k != "content"},
    )


class GreenhouseConnector:
    name = "greenhouse"
    label = "Greenhouse"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True

    def __init__(
        self,
        client: httpx.Client,
        *,
        delay_seconds: float = 1.0,
        max_boards: int = 25,
        max_jobs: int = 1000,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._delay = delay_seconds
        self._max_boards = max_boards
        self._max_jobs = max_jobs
        self._sleep = sleep

    def _get(self, url: str, params: dict[str, str] | None = None) -> Any:
        try:
            response = self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise ConnectorError("Greenhouse timed out") from exc
        except httpx.HTTPError as exc:
            raise ConnectorError("Could not reach Greenhouse") from exc
        if response.status_code == 404:
            raise ConnectorError("Board not found")
        if response.status_code == 429:
            raise ConnectorError("Greenhouse rate limit reached; try again later")
        if response.status_code >= 400:
            raise ConnectorError(f"Greenhouse returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError("Greenhouse returned an unexpected response") from exc

    def board_name(self, token: str) -> str:
        if not valid_token(token):
            raise ConnectorError("Board tokens contain only lowercase letters, digits, - and _")
        data = self._get(f"{API}/{token}")
        name = data.get("name") if isinstance(data, dict) else None
        return str(name or token)

    def fetch_job(self, token: str, job_id: str) -> RawPosting:
        if not valid_token(token) or not job_id.isdigit():
            raise ConnectorError("Not a valid Greenhouse job link")
        job = self._get(f"{API}/{token}/jobs/{job_id}", {"pay_transparency": "true"})
        if not isinstance(job, dict) or "id" not in job:
            raise ConnectorError("Greenhouse returned an unexpected response")
        return to_posting(job, token, self.board_name(token))

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        boards = [t.split("|")[0] for t in query.targets if valid_token(t.split("|")[0])]
        boards = boards[: self._max_boards]
        if not boards:
            raise ConnectorError("No Greenhouse boards configured")
        failures = 0
        for i, token in enumerate(boards):
            if i:
                self._sleep(self._delay)  # be polite between boards
            try:
                data = self._get(f"{API}/{token}/jobs", {"content": "true"})
            except ConnectorError as exc:
                failures += 1
                report.errors.append(f"{token}: {exc}")
                continue
            jobs = data.get("jobs") if isinstance(data, dict) else None
            if not isinstance(jobs, list):
                failures += 1
                report.errors.append(f"{token}: unexpected response")
                continue
            # The cap is per board, so one large company can't crowd out the others.
            for job in [j for j in jobs if isinstance(j, dict) and "id" in j][: self._max_jobs]:
                yield to_posting(job, token, token)
        if failures == len(boards):
            raise ConnectorError("; ".join(report.errors))
