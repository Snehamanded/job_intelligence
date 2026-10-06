"""Remote-job feeds: Remote OK, Remotive, Himalayas (Tier A); We Work Remotely, Jobspresso (B).

All are linked back to and named as the source, and fetched at modest rates.
Verified 2026-10-06: see docs/SOURCE_FEASIBILITY.md.
"""

import re
from collections.abc import Iterator
from typing import Any

import httpx

from app.connectors import rss
from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.common import employment, https_or_none, parse_time, structured_salary
from app.connectors.http import get_json
from app.services.jobs.normalize import RawPosting
from app.utils.html_text import html_to_text
from app.utils.salary import Period, parse_salary


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


def _get_text(client: httpx.Client, url: str, label: str) -> str:
    try:
        response = client.get(url, headers={"Accept": "application/rss+xml, application/xml"})
    except httpx.HTTPError as exc:
        raise ConnectorError(f"Could not reach {label}") from exc
    if response.status_code >= 400:
        raise ConnectorError(f"{label} returned HTTP {response.status_code}")
    return response.text


_FLAGS = re.compile(r"[\U0001F1E6-\U0001F1FF]")


class WeWorkRemotelyConnector:
    """We Work Remotely public RSS (Tier B). One feed request per search, at most hourly."""

    name = "weworkremotely"
    label = "We Work Remotely"
    tier: Tier = "B"
    is_mock = False
    needs_targets = True
    URL = "https://weworkremotely.com/remote-jobs.rss"

    def __init__(
        self, client: httpx.Client, *, min_interval_seconds: int = 3600, max_jobs: int = 1000
    ):
        self._client = client
        self.min_interval_seconds = min_interval_seconds
        self._max_jobs = max_jobs

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        for item in rss.items(_get_text(self._client, self.URL, self.label), self.label)[
            : self._max_jobs
        ]:
            yield to_wwr(item)


def to_wwr(item: dict[str, str]) -> RawPosting:
    company, _, title = item.get("title", "").partition(": ")
    if not title:
        company, title = "", company
    region = item.get("region", "")
    countries = [
        " ".join(_FLAGS.sub("", c).split()).removeprefix("and ").strip()
        for c in re.split(r",\s*", item.get("country", ""))
    ]
    if "anywhere" in region.lower() or not any(countries):
        location = "Remote, Worldwide" if "anywhere" in region.lower() else "Remote"
    else:
        location = "; ".join(f"Remote, {c}" for c in countries if c)
    link = https_or_none(item.get("link"))
    return RawPosting(
        source="weworkremotely",
        source_job_id=(item.get("guid") or link or title)[-200:],
        title=title.strip() or "Untitled role",
        company=company.strip() or "Unknown company",
        location_text=location,
        description_text=html_to_text(item.get("description", "")),
        url=link,
        posted_at=rss.rfc822(item.get("pubDate")),
        employment_hint=employment(item.get("type")),
        raw={k: v for k, v in item.items() if k != "description"},
    )


class JobspressoConnector:
    """Jobspresso public RSS (Tier B). robots.txt: no query strings, Crawl-delay 3."""

    name = "jobspresso"
    label = "Jobspresso"
    tier: Tier = "B"
    is_mock = False
    needs_targets = True
    URL = (
        "https://jobspresso.co/jobs/feed/"  # the query-string feed URL is disallowed by robots.txt
    )

    def __init__(self, client: httpx.Client, *, min_interval_seconds: int = 3600):
        self._client = client
        self.min_interval_seconds = min_interval_seconds

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        for item in rss.items(_get_text(self._client, self.URL, self.label), self.label):
            yield to_jobspresso(item)


def to_jobspresso(item: dict[str, str]) -> RawPosting:
    # dc:creator carries "Company<br>⚲ Location".
    creator = [p.strip() for p in re.split(r"<br\s*/?>", item.get("creator", ""))]
    company = html_to_text(creator[0]) if creator and creator[0] else "Unknown company"
    place = html_to_text(creator[1]).lstrip("⚲").strip() if len(creator) > 1 else ""
    link = https_or_none(item.get("link"))
    return RawPosting(
        source="jobspresso",
        source_job_id=(item.get("guid") or link or item.get("title", ""))[-200:],
        title=item.get("title", "Untitled role"),
        company=company,
        location_text=f"Remote, {place}" if place else "Remote",
        description_text=html_to_text(item.get("encoded") or item.get("description", "")),
        url=link,
        posted_at=rss.rfc822(item.get("pubDate")),
        raw={k: v for k, v in item.items() if k not in ("encoded", "description")},
    )


_HIMALAYAS_PERIODS: dict[str, Period] = {"annual": "year", "yearly": "year", "monthly": "month",
                                         "hourly": "hour"}  # fmt: skip


class HimalayasConnector:
    """Himalayas public jobs API (Tier A). Link back and name Himalayas; data refreshes daily."""

    name = "himalayas"
    label = "Himalayas"
    tier: Tier = "A"
    is_mock = False
    needs_targets = True
    URL = "https://himalayas.app/jobs/api/search"
    MAX_PAGES = 3  # 20 jobs per page; keep requests few

    def __init__(self, client: httpx.Client, *, min_interval_seconds: int = 6 * 3600):
        self._client = client
        self.min_interval_seconds = min_interval_seconds

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        # Target is a country name ("India") or "*" for worldwide-open roles.
        for target in query.targets:
            country = target.split("|")[0]
            terms = query.keywords or [""]
            for term in terms[:3]:
                for page in range(1, self.MAX_PAGES + 1):
                    params = {"q": term, "page": str(page)}
                    if country != "*":
                        params["country"] = country
                    data = get_json(self._client, self.URL, self.label, params)
                    jobs = data.get("jobs") if isinstance(data, dict) else None
                    if not isinstance(jobs, list) or not jobs:
                        break
                    for job in jobs:
                        if isinstance(job, dict) and job.get("guid"):
                            yield to_himalayas(job)
                    if len(jobs) < 20:
                        break


def to_himalayas(job: dict[str, Any]) -> RawPosting:
    regions = [r for r in job.get("locationRestrictions") or [] if isinstance(r, str)]
    location = "; ".join(f"Remote, {r}" for r in regions) or "Remote, Worldwide"
    salary = structured_salary(
        job.get("minSalary"), job.get("maxSalary"), job.get("currency"),
        _HIMALAYAS_PERIODS.get(str(job.get("salaryPeriod", "")).lower(), "year"),
    ) if str(job.get("salaryPeriod", "")).lower() in _HIMALAYAS_PERIODS else None  # fmt: skip
    return RawPosting(
        source="himalayas",
        source_job_id=str(job["guid"])[-200:],
        title=str(job.get("title") or "Untitled role"),
        company=str(job.get("companyName") or "Unknown company"),
        location_text=location,
        description_text=html_to_text(str(job.get("description") or job.get("excerpt") or "")),
        url=https_or_none(job.get("applicationLink") or job.get("guid")),
        posted_at=parse_time(job.get("pubDate")),
        salary=salary,
        employment_hint=employment(job.get("employmentType")),
        raw={k: v for k, v in job.items() if k not in ("description", "excerpt", "companyLogo")},
    )
