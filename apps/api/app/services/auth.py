import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User, UserSettings
from app.repositories.settings import SettingsRepository
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._settings = SettingsRepository(session)

    def register(self, email: str, password: str) -> User:
        email = normalize_email(email)
        if self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError
        try:
            user = self._users.add(User(email=email, password_hash=hash_password(password)))
            self._settings.add(UserSettings(user_id=user.id))
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise EmailAlreadyRegisteredError from exc
        logger.info("user_registered", extra={"user_id": str(user.id)})
        return user

    def authenticate(self, email: str, password: str) -> User | None:
        user = self._users.get_by_email(normalize_email(email))
        ok = verify_password(password, user.password_hash if user else None)
        if user is None or not ok or not user.is_active:
            logger.info("login_failed")
            return None
        logger.info("login_succeeded", extra={"user_id": str(user.id)})
        return user
