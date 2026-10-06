import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Resume


class ResumeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume | None:
        return self._session.scalar(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )

    def list(self, user_id: uuid.UUID) -> list[Resume]:
        return list(
            self._session.scalars(
                select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
            )
        )

    def add(self, resume: Resume) -> Resume:
        self._session.add(resume)
        self._session.flush()
        return resume

    def delete(self, resume: Resume) -> None:
        self._session.delete(resume)
        self._session.flush()
