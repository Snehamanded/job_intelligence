import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.adzuna import COUNTRIES
from app.connectors.base import ConnectorError
from app.connectors.registry import BOARD_SOURCES, TOGGLE_IDENTIFIERS, TOGGLE_SOURCES, Connectors
from app.core.config import Settings
from app.models import JobSourceConfig


class SourceConfigError(Exception):
    """Message is safe to show the user."""


class JobSourceService:
    def __init__(self, session: Session, user_id: uuid.UUID, settings: Settings) -> None:
        self._session = session
        self._user_id = user_id
        self._settings = settings

    def list(self) -> list[JobSourceConfig]:
        return list(
            self._session.scalars(
                select(JobSourceConfig)
                .where(JobSourceConfig.user_id == self._user_id)
                .order_by(JobSourceConfig.created_at)
            )
        )

    def get(self, config_id: uuid.UUID) -> JobSourceConfig | None:
        return self._session.scalar(
            select(JobSourceConfig).where(
                JobSourceConfig.id == config_id, JobSourceConfig.user_id == self._user_id
            )
        )

    def add(
        self, source: str, identifier: str, display_name: str | None, connectors: Connectors
    ) -> JobSourceConfig:
        identifier = identifier.strip()
        if source in BOARD_SOURCES:
            identifier = identifier.lower() if source == "greenhouse" else identifier
            boards = [c for c in self.list() if c.source in BOARD_SOURCES]
            if len(boards) >= self._settings.max_job_boards:
                raise SourceConfigError(
                    f"You can add up to {self._settings.max_job_boards} boards."
                )
            validate = {
                "greenhouse": connectors.greenhouse.board_name,
                "lever": connectors.lever.validate,
                "ashby": connectors.ashby.validate,
            }[source]
            try:
                name = validate(identifier)
            except ConnectorError as exc:
                raise SourceConfigError(f"Could not add '{identifier}': {exc}") from exc
            name = (display_name or "").strip() or name
        elif source in TOGGLE_SOURCES:
            identifier, name = TOGGLE_IDENTIFIERS.get(source, "*"), source
            # A switched-off feed keeps its row (so defaults don't switch it back on).
            existing = next((c for c in self.list() if c.source == source), None)
            if existing is not None and not existing.enabled:
                existing.enabled = True
                self._session.commit()
                return existing
        elif source == "adzuna":
            if connectors.adzuna is None:
                raise SourceConfigError("Adzuna isn't configured on this server.")
            identifier = identifier.lower() or "in"
            if identifier not in COUNTRIES:
                raise SourceConfigError("Choose a supported Adzuna country code, e.g. 'in'.")
            name = f"Adzuna ({identifier.upper()})"
        else:
            raise SourceConfigError("Unknown source")
        config = JobSourceConfig(user_id=self._user_id, source=source, identifier=identifier,
                                 display_name=name[:200], enabled=True)  # fmt: skip
        self._session.add(config)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise SourceConfigError(f"'{identifier}' is already added.") from exc
        return config

    def delete(self, config: JobSourceConfig) -> None:
        if config.source in TOGGLE_SOURCES:
            config.enabled = False
        else:
            self._session.delete(config)
        self._session.commit()

    def ensure_defaults(self, connectors: Connectors) -> None:
        """On first use, switch on the default sources so a search works without any setup."""
        if not self._settings.default_sources_enabled or self._session.scalar(
            select(JobSourceConfig.id).where(JobSourceConfig.user_id == self._user_id).limit(1)
        ):
            return
        rows = [(s, TOGGLE_IDENTIFIERS.get(s, "*"), s) for s in TOGGLE_SOURCES]
        if connectors.adzuna is not None:
            rows.append(("adzuna", "in", "Adzuna (IN)"))
        boards = []
        for entry in self._settings.starter_company_boards.split(","):
            source, _, rest = entry.strip().partition(":")
            identifier, _, name = rest.partition(":")
            if source in BOARD_SOURCES and identifier:
                boards.append((source, identifier, name or identifier.title()))
        rows += boards[: self._settings.max_job_boards]
        self._session.add_all(
            JobSourceConfig(user_id=self._user_id, source=source, identifier=identifier,
                            display_name=name[:200], enabled=True)
            for source, identifier, name in rows
        )  # fmt: skip
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()  # another request seeded them first
