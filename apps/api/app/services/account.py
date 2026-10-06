import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationNote,
    CoverLetter,
    Interview,
    LLMUsage,
    ResumeVersion,
    User,
)
from app.repositories.profiles import ProfileRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.settings import SettingsRepository
from app.services.profile import preferences_of
from app.services.storage import LocalFileStorage

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, session: Session, storage: LocalFileStorage) -> None:
        self._session = session
        self._storage = storage

    def export(self, user: User) -> dict[str, Any]:
        """Everything stored about the user, as JSON-serializable data."""
        settings = SettingsRepository(self._session).get_for_user(user.id)
        usage = self._session.scalars(
            select(LLMUsage).where(LLMUsage.user_id == user.id).order_by(LLMUsage.created_at)
        )
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            },
            "settings": {
                "llm_consent": settings.llm_consent if settings else False,
                "llm_consent_at": settings.llm_consent_at.isoformat()
                if settings and settings.llm_consent_at
                else None,
            },
            "resumes": [
                {
                    "id": str(r.id),
                    "original_filename": r.original_filename,
                    "file_type": r.file_type,
                    "size_bytes": r.size_bytes,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                    "extracted_text": r.extracted_text,
                }
                for r in ResumeRepository(self._session).list(user.id)
            ],
            "profiles": [
                {
                    "version": p.version,
                    "is_current": p.is_current,
                    "origin": p.origin,
                    "parse_method": p.parse_method,
                    "created_at": p.created_at.isoformat(),
                    "experience_months": p.experience_months,
                    "data": p.data,
                    "preferences": preferences_of(p).model_dump(),
                }
                for p in ProfileRepository(self._session).versions(user.id)
            ],
            "applications": self._applications(user),
            "cover_letters": [
                {
                    "version": c.version,
                    "name": c.name,
                    "job_title": c.job_title,
                    "company": c.company,
                    "status": c.status,
                    "tone": c.tone,
                    "paragraphs": c.paragraphs,
                    "content": c.content,
                    "created_at": c.created_at.isoformat(),
                }
                for c in self._session.scalars(
                    select(CoverLetter).where(CoverLetter.user_id == user.id)
                )
            ],
            "resume_versions": [
                {
                    "version": v.version,
                    "name": v.name,
                    "job_title": v.job_title,
                    "company": v.company,
                    "status": v.status,
                    "changes": v.changes,
                    "content": v.content,
                    "created_at": v.created_at.isoformat(),
                }
                for v in self._session.scalars(
                    select(ResumeVersion).where(ResumeVersion.user_id == user.id)
                )
            ],
            "llm_usage": [
                {
                    "task": u.task,
                    "provider": u.provider,
                    "model": u.model,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "success": u.success,
                    "created_at": u.created_at.isoformat(),
                }
                for u in usage
            ],
        }

    def delete(self, user: User, password: str) -> bool:
        if not verify_password(password, user.password_hash):
            return False
        user_id: uuid.UUID = user.id
        self._session.delete(user)  # cascades to every user-owned table
        self._session.commit()
        self._storage.delete_user(user_id)
        logger.info("account_deleted", extra={"user_id": str(user_id)})
        return True

    def _applications(self, user: User) -> list[dict[str, Any]]:
        def rows(model: Any) -> list[Any]:
            return list(self._session.scalars(select(model).where(model.user_id == user.id)))

        notes, interviews, events = rows(ApplicationNote), rows(Interview), rows(ApplicationEvent)
        result = []
        for app in rows(Application):
            result.append(
                {
                    "title": app.title, "company": app.company, "location": app.location,
                    "url": app.url, "source": app.source, "stage": app.stage,
                    "match_score": app.match_score,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "next_action": app.next_action,
                    "notes": [{"body": n.body, "created_at": n.created_at.isoformat()}
                              for n in notes if n.application_id == app.id],
                    "interviews": [
                        {"scheduled_at": i.scheduled_at.isoformat(), "kind": i.kind,
                         "location": i.location, "outcome": i.outcome, "notes": i.notes,
                         "checklist": i.checklist}
                        for i in interviews if i.application_id == app.id
                    ],
                    "history": [
                        {"kind": e.kind, "from": e.from_stage, "to": e.to_stage,
                         "at": e.created_at.isoformat()}
                        for e in events if e.application_id == app.id
                    ],
                }
            )  # fmt: skip
        return result
