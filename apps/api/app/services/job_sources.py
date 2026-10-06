import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.greenhouse import GreenhouseConnector, valid_token
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

    def add_greenhouse_board(self, token: str, greenhouse: GreenhouseConnector) -> JobSourceConfig:
        token = token.strip().lower()
        if not valid_token(token):
            raise SourceConfigError(
                "Enter the board token from the careers URL, e.g. 'gitlab' from "
                "job-boards.greenhouse.io/gitlab."
            )
        if len(self.list()) >= self._settings.max_greenhouse_boards:
            raise SourceConfigError(
                f"You can add up to {self._settings.max_greenhouse_boards} boards."
            )
        try:
            name = greenhouse.board_name(token)  # validates that the board exists
        except ConnectorError as exc:
            raise SourceConfigError(f"Could not add '{token}': {exc}") from exc
        config = JobSourceConfig(
            user_id=self._user_id, source="greenhouse", identifier=token, display_name=name[:200],
            enabled=True,
        )  # fmt: skip
        self._session.add(config)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise SourceConfigError(f"'{token}' is already added.") from exc
        return config

    def delete(self, config: JobSourceConfig) -> None:
        self._session.delete(config)
        self._session.commit()
