"""Adzuna job search API (Tier A, keyed). Off until ADZUNA_APP_ID/ADZUNA_APP_KEY are set.

Built from the documented response format (developer.adzuna.com, 2026-10-06); not yet verified
against the live API. Predicted salaries are ignored: we never guess a salary.
"""

from collections.abc import Iterator
from typing import Any

import httpx

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.common import employment, https_or_none, parse_time, structured_salary
from app.connectors.http import get_json
from app.services.jobs.normalize import RawPosting

API = "https://api.adzuna.com/v1/api/jobs"
COUNTRIES = {"in": "INR", "gb": "GBP", "us": "USD", "ca": "CAD", "au": "AUD", "de": "EUR",
             "fr": "EUR", "nl": "EUR", "sg": "SGD", "nz": "NZD"}  # fmt: skip
PER_PAGE = 50


def to_posting(job: dict[str, Any], country: str) -> RawPosting:
    loc = job.get("location") or {}
    area = [a for a in loc.get("area") or [] if isinstance(a, str)]
    location = loc.get("display_name") or ""
    if area and area[0] not in location:
        location = f"{location}, {area[0]}".strip(", ")
    predicted = str(job.get("salary_is_predicted", "1")) not in ("0", "False", "false")
    salary = None if predicted else structured_salary(
        job.get("salary_min"), job.get("salary_max"), COUNTRIES[country], "year"
    )  # fmt: skip
    return RawPosting(
        source="adzuna",
        source_job_id=f"{country}:{job.get('id')}",
        title=str(job.get("title") or "Untitled role"),
        company=str((job.get("company") or {}).get("display_name") or "Unknown company"),
        location_text=location,
        # Adzuna returns only a snippet; the full posting is behind redirect_url.
        description_text=str(job.get("description") or ""),
        url=https_or_none(job.get("redirect_url")),
        posted_at=parse_time(job.get("created")),
        salary=salary,
        employment_hint=employment(job.get("contract_time"))
        or employment(job.get("contract_type")),
        raw={k: v for k, v in job.items() if k != "description"},
    )


class AdzunaConnector:
    name = "adzuna"
    label = "Adzuna"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True
    min_interval_seconds = 3600

    def __init__(self, client: httpx.Client, *, app_id: str, app_key: str, max_jobs: int = 200):
        self._client = client
        self._auth = {"app_id": app_id, "app_key": app_key}
        self._max_jobs = max_jobs

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        countries = [c for c in query.targets if c in COUNTRIES]
        if not countries:
            raise ConnectorError("No Adzuna country configured")
        yielded = 0
        for country in countries:
            params = {**self._auth, "results_per_page": str(PER_PAGE), "max_days_old": "30",
                      "content-type": "application/json"}  # fmt: skip
            if query.keywords:
                params["what_or"] = " ".join(query.keywords)
            try:
                data = get_json(self._client, f"{API}/{country}/search/1", self.label, params)
            except ConnectorError as exc:
                report.errors.append(f"{country}: {exc}")
                continue
            for job in (data.get("results") or []) if isinstance(data, dict) else []:
                if isinstance(job, dict) and "id" in job and yielded < self._max_jobs:
                    yielded += 1
                    yield to_posting(job, country)
        if len(report.errors) == len(countries):
            raise ConnectorError("; ".join(report.errors))
