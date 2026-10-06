"""Lever Postings API (Tier A). Verified 2026-10-06: see docs/SOURCE_FEASIBILITY.md."""

import re
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.common import SLUG_RE, employment, parse_time, structured_salary
from app.connectors.http import get_json
from app.services.jobs.normalize import RawPosting
from app.utils.html_text import html_to_text
from app.utils.salary import Period

API = {"global": "https://api.lever.co/v0/postings", "eu": "https://api.eu.lever.co/v0/postings"}
PAGE = 100
JOB_URL_RE = re.compile(
    r"^https://jobs(?P<eu>\.eu)?\.lever\.co/(?P<site>[A-Za-z0-9_.-]+)/(?P<id>[0-9a-f-]{36})"
)
_PERIODS: dict[str, Period] = {"per-year-salary": "year", "per-month-salary": "month",
                               "per-hour-wage": "hour"}  # fmt: skip


def parse_job_url(url: str) -> tuple[str, str, str] | None:
    """(region, site, posting_id) from a public Lever job URL."""
    m = JOB_URL_RE.match(url.strip())
    if not m:
        return None
    return ("eu" if m.group("eu") else "global"), m.group("site"), m.group("id")


def to_posting(p: dict[str, Any], site: str, company: str) -> RawPosting:
    cats = p.get("categories") or {}
    location = cats.get("location") or ""
    others = [loc for loc in cats.get("allLocations") or [] if loc and loc != location]
    places = "; ".join([location, *others]) if location else "; ".join(others)
    workplace = (p.get("workplaceType") or "").lower()
    if workplace == "remote":
        places = f"Remote, {places or p.get('country') or ''}".strip(" ,")
    elif workplace == "hybrid" and places:
        places = f"Hybrid - {places}"
    parts = [p.get("descriptionPlain") or html_to_text(p.get("description") or "")]
    for block in p.get("lists") or []:
        parts.append(f"{block.get('text', '')}\n{html_to_text(block.get('content') or '')}")
    parts.append(p.get("additionalPlain") or "")
    salary = None
    sr = p.get("salaryRange")
    if isinstance(sr, dict):
        salary = structured_salary(sr.get("min"), sr.get("max"), sr.get("currency"),
                                   _PERIODS.get(str(sr.get("interval")), "year"))  # fmt: skip
    return RawPosting(
        source="lever",
        source_job_id=f"{site}:{p['id']}",
        title=str(p.get("text") or "Untitled role"),
        company=company,
        location_text=places,
        description_text="\n\n".join(x.strip() for x in parts if x and x.strip()),
        url=p.get("hostedUrl") if str(p.get("hostedUrl", "")).startswith("https://") else None,
        posted_at=parse_time(p.get("createdAt")),
        salary=salary,
        employment_hint=employment(cats.get("commitment")),
        raw={k: v for k, v in p.items() if k not in ("description", "descriptionPlain", "lists",
                                                       "additional", "additionalPlain")},
    )  # fmt: skip


class LeverConnector:
    name = "lever"
    label = "Lever"
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
        self._delay = max(delay_seconds, 1.0)  # robots.txt: Crawl-delay 1
        self._max_jobs = max_jobs
        self._sleep = sleep

    def validate(self, site: str) -> str:
        if not SLUG_RE.fullmatch(site):
            raise ConnectorError("Use the company name from its jobs.lever.co link")
        get_json(self._client, f"{API['global']}/{site}", "Lever", {"mode": "json", "limit": "1"})
        return site.replace("-", " ").title()

    def fetch_job(self, region: str, site: str, posting_id: str, company: str) -> RawPosting:
        data = get_json(
            self._client, f"{API[region]}/{site}/{posting_id}", "Lever", {"mode": "json"}
        )
        if not isinstance(data, dict) or "id" not in data:
            raise ConnectorError("Lever returned an unexpected response")
        return to_posting(data, site, company)

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        sites = [t for t in query.targets if SLUG_RE.fullmatch(t.split("|")[0])]
        if not sites:
            raise ConnectorError("No Lever companies configured")
        failures = 0
        first = True
        for target in sites:
            site, _, company = target.partition("|")
            company = company or site.title()
            skip = yielded = 0  # the cap is per company
            while yielded < self._max_jobs:
                if not first:
                    self._sleep(self._delay)
                first = False
                params = {"mode": "json", "skip": str(skip), "limit": str(PAGE)}
                try:
                    page = get_json(self._client, f"{API['global']}/{site}", "Lever", params)
                except ConnectorError as exc:
                    failures += 1
                    report.errors.append(f"{site}: {exc}")
                    break
                if not isinstance(page, list):
                    failures += 1
                    report.errors.append(f"{site}: unexpected response")
                    break
                for p in page:
                    if isinstance(p, dict) and "id" in p and yielded < self._max_jobs:
                        yielded += 1
                        yield to_posting(p, site, company)
                if len(page) < PAGE:
                    break
                skip += PAGE
        if failures == len(sites):
            raise ConnectorError("; ".join(report.errors))
