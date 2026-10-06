import hashlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Resume
from app.repositories.resumes import ResumeRepository
from app.services.resume.documents import safe_display_name, validate_upload
from app.services.storage import FileStorage
from app.workers.queue import TaskQueue

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(
        self, session: Session, settings: Settings, storage: FileStorage, queue: TaskQueue
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._queue = queue
        self._repo = ResumeRepository(session)

    def upload(self, user_id: uuid.UUID, filename: str | None, data: bytes) -> Resume:
        file_type = validate_upload(filename, data, self._settings)
        key = self._storage.save(user_id, data, file_type)
        try:
            resume = self._repo.add(
                Resume(
                    user_id=user_id,
                    original_filename=safe_display_name(filename),
                    file_type=file_type,
                    size_bytes=len(data),
                    file_sha256=hashlib.sha256(data).hexdigest(),
                    storage_key=key,
                    status="queued",
                )
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            self._storage.delete(key)
            raise
        logger.info(
            "resume_uploaded",
            extra={"resume_id": str(resume.id), "file_type": file_type, "size_bytes": len(data)},
        )
        self._queue.enqueue_parse(user_id, resume.id)
        return resume

    def reparse(self, resume: Resume) -> Resume:
        resume.status, resume.error_message, resume.parse_notice = "queued", None, None
        self._session.commit()
        self._queue.enqueue_parse(resume.user_id, resume.id)
        return resume

    def get(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume | None:
        return self._repo.get(user_id, resume_id)

    def list(self, user_id: uuid.UUID) -> list[Resume]:
        return self._repo.list(user_id)

    def read_file(self, resume: Resume) -> bytes:
        return self._storage.read(resume.storage_key)

    def delete(self, resume: Resume) -> None:
        key = resume.storage_key
        self._repo.delete(resume)
        self._session.commit()
        self._storage.delete(key)
        logger.info("resume_deleted", extra={"resume_id": str(resume.id)})
