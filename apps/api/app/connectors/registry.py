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
from app.connectors.remote_feeds import RemoteOKConnector, RemotiveConnector
from app.connectors.safe_http import Resolver, SafeFetcher, system_resolver
from app.core.config import Settings

ConfigKind = Literal["boards", "toggle", "country", "none"]


@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    label: str
    tier: Tier
    kind: str  # "real" | "mock" | "manual_only"
    enabled: bool
    note: str
    config: ConfigKind = "none"
    attribution: str | None = None


# Tier C sources: interface + mock + manual import only (docs/SOURCE_FEASIBILITY.md).
MOCK_SOURCES = [("linkedin", "LinkedIn"), ("naukri", "Naukri"), ("indeed", "Indeed")]
BOARD_SOURCES = ("greenhouse", "lever", "ashby")
TOGGLE_SOURCES = ("remoteok", "remotive")


@dataclass
class Connectors:
    """Every connector, built with one HTTP client. Tests pass a MockTransport."""

    greenhouse: GreenhouseConnector
    lever: LeverConnector
    ashby: AshbyConnector
    remoteok: RemoteOKConnector
    remotive: RemotiveConnector
    adzuna: AdzunaConnector | None
    fetcher: SafeFetcher

    def for_search(self, settings: Settings) -> list[JobConnector]:
        found: list[JobConnector] = [
            self.greenhouse,
            self.lever,
            self.ashby,
            self.remoteok,
            self.remotive,
        ]
        if self.adzuna is not None:
            found.append(self.adzuna)
        if settings.enable_mock_connectors:
            found += [MockConnector(name, label) for name, label in MOCK_SOURCES]
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
    infos = [
        ConnectorInfo("greenhouse", "Greenhouse", "A", "real", True,
                      "Company career boards on Greenhouse.", "boards"),
        ConnectorInfo("lever", "Lever", "A", "real", True,
                      "Company career sites on Lever (jobs.lever.co/<company>).", "boards"),
        ConnectorInfo("ashby", "Ashby", "A", "real", True,
                      "Company job boards on Ashby (jobs.ashbyhq.com/<company>).", "boards"),
        ConnectorInfo("remoteok", "Remote OK", "A", "real", True,
                      "Global remote jobs. Checked at most once an hour.", "toggle",
                      "Jobs via Remote OK, linked back to the original listing."),
        ConnectorInfo("remotive", "Remotive", "A", "real", True,
                      "Global remote jobs. Remotive asks for at most a few requests a day, so it "
                      "is checked at most every 6 hours.", "toggle",
                      "Jobs via Remotive, linked back to the original listing."),
        ConnectorInfo("adzuna", "Adzuna", "A", "real", adzuna_ready,
                      "Job search aggregator with India listings. Salaries Adzuna estimates are "
                      "ignored." + ("" if adzuna_ready else
                                   " Needs ADZUNA_APP_ID and ADZUNA_APP_KEY on the server."),
                      "country"),
        ConnectorInfo("smartrecruiters", "SmartRecruiters", "C", "manual_only", False,
                      "Its robots.txt disallows automated access, so import individual jobs by "
                      "link instead."),
    ]  # fmt: skip
    for name, label in MOCK_SOURCES:
        infos.append(
            ConnectorInfo(
                name, label, "C", "mock", settings.enable_mock_connectors,
                "No public API; automated access is restricted. Use manual import for real "
                "postings. The mock (fictional jobs) is for development only.",
            )
        )  # fmt: skip
    return infos


__all__ = ["BOARD_SOURCES", "COUNTRIES", "TOGGLE_SOURCES", "ConnectorInfo", "Connectors", "build"]
