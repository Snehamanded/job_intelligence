from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.services.jobs.normalize import RawPosting

Tier = Literal["A", "B", "C"]


class ConnectorError(Exception):
    """A source could not be fetched. The message is safe to show the user."""


@dataclass(frozen=True)
class SearchQuery:
    keywords: list[str]
    # Source-specific targets, e.g. Greenhouse board tokens.
    targets: list[str] = field(default_factory=list)


@dataclass
class FetchReport:
    """Per-target problems that did not stop the whole source."""

    errors: list[str] = field(default_factory=list)


class JobConnector(Protocol):
    name: str
    label: str
    tier: Tier
    is_mock: bool
    needs_targets: bool

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        """Yield postings. Raise ConnectorError if the source cannot be used at all."""
        ...
