import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import CandidateProfile


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current(self, user_id: uuid.UUID) -> CandidateProfile | None:
        return self._session.scalar(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id, CandidateProfile.is_current.is_(True)
            )
        )

    def versions(self, user_id: uuid.UUID) -> list[CandidateProfile]:
        return list(
            self._session.scalars(
                select(CandidateProfile)
                .where(CandidateProfile.user_id == user_id)
                .order_by(CandidateProfile.version.desc())
            )
        )

    def add_version(self, profile: CandidateProfile) -> CandidateProfile:
        """Insert as the new current version. Locks the user's rows to serialize version numbers."""
        user_id = profile.user_id
        self._session.execute(
            select(CandidateProfile.id).where(CandidateProfile.user_id == user_id).with_for_update()
        )
        latest = self._session.scalar(
            select(func.max(CandidateProfile.version)).where(CandidateProfile.user_id == user_id)
        )
        self._session.execute(
            update(CandidateProfile)
            .where(CandidateProfile.user_id == user_id, CandidateProfile.is_current.is_(True))
            .values(is_current=False)
        )
        profile.version = (latest or 0) + 1
        profile.is_current = True
        self._session.add(profile)
        self._session.flush()
        return profile
