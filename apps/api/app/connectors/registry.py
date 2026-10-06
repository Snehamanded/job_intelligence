import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import httpx

from app.connectors.adzuna import COUNTRIES, AdzunaConnector
from app.connectors.ashby import AshbyConnector
from app.connectors.base import JobConnector, Tier
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.http import make_client
from app.connectors.lever import LeverConnector
from app.connectors.mock import MockConnector
from app.connectors.remote_feeds import (
    HimalayasConnector,
    JobspressoConnector,
    RemoteOKConnector,
    RemotiveConnector,
    WeWorkRemotelyConnector,
)
from app.connectors.safe_http import Resolver, SafeFetcher, system_resolver
from app.core.config import Settings

ConfigKind = Literal["boards", "toggle", "country", "none"]
Category = Literal["general", "india", "startup", "remote", "ats"]


@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    label: str
    tier: Tier
    kind: str  # "real" | "import" | "mock" | "manual_only"
    enabled: bool
    note: str
    config: ConfigKind = "none"
    attribution: str | None = None
    category: Category = "general"


# Tier C sources: interface + mock + manual import only (docs/SOURCE_FEASIBILITY.md).
MOCK_SOURCES: list[tuple[str, str, Category]] = [
    ("linkedin", "LinkedIn", "general"), ("indeed", "Indeed", "general"),
    ("glassdoor", "Glassdoor", "general"), ("ziprecruiter", "ZipRecruiter", "general"),
    ("naukri", "Naukri", "india"), ("foundit", "Foundit", "india"), ("shine", "Shine", "india"),
    ("apna", "Apna", "india"),
    ("wellfound", "Wellfound", "startup"), ("instahyre", "Instahyre", "startup"),
    ("cutshort", "Cutshort", "startup"), ("hirist", "Hirist", "startup"),
]  # fmt: skip
BOARD_SOURCES = ("greenhouse", "lever", "ashby")
TOGGLE_SOURCES = ("remoteok", "remotive", "weworkremotely", "jobspresso", "himalayas")
# Identifier stored for a switched-on feed: Himalayas searches roles open to India.
TOGGLE_IDENTIFIERS = {"himalayas": "India"}
# Career-portal platforms supported through link import (pages' JobPosting data).
IMPORT_PLATFORMS: list[tuple[str, str]] = [
    ("workday", "Workday"), ("smartrecruiters", "SmartRecruiters"), ("icims", "iCIMS"),
    ("taleo", "Taleo"), ("successfactors", "SAP SuccessFactors"),
]  # fmt: skip


@dataclass
class Connectors:
    """Every connector, built with one HTTP client. Tests pass a MockTransport."""

    greenhouse: GreenhouseConnector
    lever: LeverConnector
    ashby: AshbyConnector
    remoteok: RemoteOKConnector
    remotive: RemotiveConnector
    weworkremotely: WeWorkRemotelyConnector
    jobspresso: JobspressoConnector
    himalayas: HimalayasConnector
    adzuna: AdzunaConnector | None
    fetcher: SafeFetcher

    def for_search(self, settings: Settings) -> list[JobConnector]:
        found: list[JobConnector] = [
            self.greenhouse,
            self.lever,
            self.ashby,
            self.remoteok,
            self.remotive,
            self.weworkremotely,
            self.jobspresso,
            self.himalayas,
        ]
        if self.adzuna is not None:
            found.append(self.adzuna)
        if settings.enable_mock_connectors:
            found += [MockConnector(name, label) for name, label, _ in MOCK_SOURCES]
        return found


def build(
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
    resolve: Resolver = system_resolver,
    sleep: Callable[[float], None] = time.sleep,
) -> Connectors:
    client = make_client(settings, transport)
    delay = settings.connector_request_delay_seconds
    adzuna = None
    if settings.adzuna_app_id and settings.adzuna_app_key:
        adzuna = AdzunaConnector(
            client,
            app_id=settings.adzuna_app_id.get_secret_value(),
            app_key=settings.adzuna_app_key.get_secret_value(),
        )
    return Connectors(
        greenhouse=GreenhouseConnector(
            client, delay_seconds=delay, max_boards=settings.max_job_boards,
            max_jobs=settings.max_jobs_per_source, sleep=sleep,
        ),
        lever=LeverConnector(
            client, delay_seconds=delay, max_jobs=settings.max_jobs_per_source, sleep=sleep
        ),
        ashby=AshbyConnector(
            client, delay_seconds=delay, max_jobs=settings.max_jobs_per_source, sleep=sleep
        ),
        remoteok=RemoteOKConnector(
            client, min_interval_seconds=settings.remoteok_min_interval_seconds
        ),
        remotive=RemotiveConnector(
            client, min_interval_seconds=settings.remotive_min_interval_seconds
        ),
        weworkremotely=WeWorkRemotelyConnector(
            client, min_interval_seconds=settings.weworkremotely_min_interval_seconds
        ),
        jobspresso=JobspressoConnector(
            client, min_interval_seconds=settings.jobspresso_min_interval_seconds
        ),
        himalayas=HimalayasConnector(
            client, min_interval_seconds=settings.himalayas_min_interval_seconds
        ),
        adzuna=adzuna,
        fetcher=SafeFetcher(
            client, user_agent=settings.connector_user_agent,
            max_bytes=settings.import_max_bytes, resolve=resolve,
        ),
    )  # fmt: skip


def greenhouse(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> GreenhouseConnector:
    return build(settings, transport).greenhouse


def build_connectors(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> list[JobConnector]:
    return build(settings, transport).for_search(settings)


def describe(settings: Settings) -> list[ConnectorInfo]:
    adzuna_ready = bool(settings.adzuna_app_id and settings.adzuna_app_key)
    feed = "Global remote jobs, linked back to the original listing."
    infos = [
        # Company career portals (ATS)
        ConnectorInfo("greenhouse", "Greenhouse", "A", "real", True,
                      "Company career boards on Greenhouse.", "boards", category="ats"),
        ConnectorInfo("lever", "Lever", "A", "real", True,
                      "Company career sites on Lever (jobs.lever.co/<company>).", "boards",
                      category="ats"),
        ConnectorInfo("ashby", "Ashby", "A", "real", True,
                      "Company job boards on Ashby (jobs.ashbyhq.com/<company>).", "boards",
                      category="ats"),
        # Remote boards
        ConnectorInfo("remoteok", "Remote OK", "A", "real", True,
                      f"{feed} Checked at most once an hour.", "toggle",
                      "Jobs via Remote OK, linked back to the original listing.", "remote"),
        ConnectorInfo("weworkremotely", "We Work Remotely", "B", "real", True,
                      f"{feed} Public RSS feed, checked at most once an hour.", "toggle",
                      "Jobs via We Work Remotely, linked back to the original listing.", "remote"),
        ConnectorInfo("remotive", "Remotive", "A", "real", True,
                      f"{feed} Remotive asks for few requests, so it's checked at most every "
                      "6 hours.", "toggle",
                      "Jobs via Remotive, linked back to the original listing.", "remote"),
        ConnectorInfo("himalayas", "Himalayas", "A", "real", True,
                      "Remote jobs open to candidates in India. Checked at most every 6 hours "
                      "(its data refreshes daily).", "toggle",
                      "Jobs via Himalayas, linked back to the original listing.", "remote"),
        ConnectorInfo("jobspresso", "Jobspresso", "B", "real", True,
                      f"{feed} Public RSS feed of its latest listings, checked at most hourly.",
                      "toggle", "Jobs via Jobspresso, linked back to the original listing.",
                      "remote"),
        # General
        ConnectorInfo("adzuna", "Adzuna", "A", "real", adzuna_ready,
                      "Job search aggregator with India listings. Salaries Adzuna estimates are "
                      "ignored." + ("" if adzuna_ready else
                                   " Needs ADZUNA_APP_ID and ADZUNA_APP_KEY on the server."),
                      "country", category="general"),
        ConnectorInfo("google_jobs", "Google Jobs", "C", "import", True,
                      "Google has no public job-search API and its results can't be scraped. "
                      "Google Jobs reads the job data companies publish on their own pages, so "
                      "import those pages by link instead.", category="general"),
    ]  # fmt: skip
    for name, label in IMPORT_PLATFORMS:
        reason = (
            "Its API host's robots.txt disallows automated access, so there's no search "
            "connector. " if name == "smartrecruiters" else
            "Each company runs its own career site with no shared public API. "
        )  # fmt: skip
        infos.append(
            ConnectorInfo(
                name, label, "B", "import", True,
                reason + "Import a job by pasting its link: the page's published job data is "
                "read where the site's robots.txt allows; otherwise paste the description.",
                category="ats",
            )
        )  # fmt: skip
    for name, label, category in MOCK_SOURCES:
        infos.append(
            ConnectorInfo(
                name, label, "C", "mock", settings.enable_mock_connectors,
                f"No public API for individuals, and {label}'s terms restrict automated access, "
                "so it is never fetched. Paste job descriptions to import them. A fictional "
                "mock exists for development.",
                category=category,
            )
        )  # fmt: skip
    return infos


__all__ = ["BOARD_SOURCES", "COUNTRIES", "TOGGLE_SOURCES", "ConnectorInfo", "Connectors", "build"]
