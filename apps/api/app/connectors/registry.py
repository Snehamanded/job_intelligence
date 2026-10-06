from dataclasses import dataclass

import httpx

from app.connectors.base import JobConnector, Tier
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.http import make_client
from app.connectors.mock import MockConnector
from app.core.config import Settings


@dataclass(frozen=True)
class ConnectorInfo:
    name: str
    label: str
    tier: Tier
    kind: str  # "real" | "mock" | "manual_only"
    enabled: bool
    note: str


# Tier C sources: interface + mock + manual import only (docs/SOURCE_FEASIBILITY.md).
MOCK_SOURCES = [("linkedin", "LinkedIn"), ("naukri", "Naukri"), ("indeed", "Indeed")]


def greenhouse(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> GreenhouseConnector:
    return GreenhouseConnector(
        make_client(settings, transport),
        delay_seconds=settings.connector_request_delay_seconds,
        max_boards=settings.max_greenhouse_boards,
        max_jobs=settings.max_jobs_per_source,
    )


def build_connectors(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> list[JobConnector]:
    connectors: list[JobConnector] = [greenhouse(settings, transport)]
    if settings.enable_mock_connectors:
        connectors += [MockConnector(name, label) for name, label in MOCK_SOURCES]
    return connectors


def describe(settings: Settings) -> list[ConnectorInfo]:
    infos = [
        ConnectorInfo("greenhouse", "Greenhouse", "A", "real", True,
                      "Company career boards. Add the boards you want searched."),
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
