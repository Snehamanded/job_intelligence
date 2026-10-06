import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserSettings


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, user_id: uuid.UUID) -> UserSettings | None:
        return self._session.scalar(select(UserSettings).where(UserSettings.user_id == user_id))

    def add(self, settings: UserSettings) -> UserSettings:
        self._session.add(settings)
        self._session.flush()
        return settings
