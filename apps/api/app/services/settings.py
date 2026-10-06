import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.repositories.settings import SettingsRepository


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SettingsRepository(session)

    def get(self, user_id: uuid.UUID) -> UserSettings:
        settings = self._repo.get_for_user(user_id)
        if settings is None:
            settings = self._repo.add(UserSettings(user_id=user_id))
            self._session.commit()
        return settings

    def update(self, user_id: uuid.UUID, *, llm_consent: bool) -> UserSettings:
        settings = self.get(user_id)
        if llm_consent != settings.llm_consent:
            settings.llm_consent = llm_consent
            settings.llm_consent_at = datetime.now(UTC) if llm_consent else None
        self._session.commit()
        return settings
