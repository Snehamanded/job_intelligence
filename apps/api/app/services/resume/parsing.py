import hashlib
import logging
import time
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.ai.providers import AIProvider
from app.ai.services.resume_extraction import ResumeExtractionService
from app.core.config import Settings
from app.models import Resume
from app.repositories.resumes import ResumeRepository
from app.repositories.settings import SettingsRepository
from app.services.profile import ProfileService, preferences_of
from app.services.resume.documents import ExtractionError, extract_text
from app.services.resume.evidence import EvidenceValidator
from app.services.resume.heuristic import heuristic_extract
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "Something went wrong while reading this resume. Please try again."


class ResumeParsingService:
    def __init__(
        self,
        session: Session,
        *,
        provider: AIProvider | None,
        settings: Settings,
        storage: FileStorage,
        today: date | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._resumes = ResumeRepository(session)
        self._profiles = ProfileService(session)
        self._ai = ResumeExtractionService(session, provider, settings)
        self._today = today

    def parse(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        resume = self._resumes.get(user_id, resume_id)
        if resume is None:
            logger.warning("resume_parse_missing", extra={"resume_id": str(resume_id)})
            return
        started = time.perf_counter()
        resume.status, resume.error_message, resume.parse_notice = "parsing", None, None
        self._session.commit()
        logger.info("resume_parse_started", extra={"resume_id": str(resume.id)})

        try:
            self._parse(resume)
        except ExtractionError as exc:
            self._session.rollback()
            self._fail(resume, str(exc))
            return
        except Exception:
            self._session.rollback()
            logger.exception("resume_parse_crashed", extra={"resume_id": str(resume.id)})
            self._fail(resume, GENERIC_FAILURE)
            raise
        logger.info(
            "resume_parse_completed",
            extra={"resume_id": str(resume.id),
                   "duration_ms": round((time.perf_counter() - started) * 1000)},
        )  # fmt: skip

    def mark_failed(self, user_id: uuid.UUID, resume_id: uuid.UUID, message: str) -> None:
        resume = self._resumes.get(user_id, resume_id)
        if resume is not None:
            self._fail(resume, message)

    def _fail(self, resume: Resume, message: str) -> None:
        resume.status, resume.error_message = "failed", message
        self._session.commit()
        logger.info("resume_parse_failed", extra={"resume_id": str(resume.id)})

    def _parse(self, resume: Resume) -> None:
        document = extract_text(
            self._storage.read(resume.storage_key),
            resume.file_type,  # type: ignore[arg-type]
            self._settings,
        )
        resume.extracted_text = document.text
        resume.text_sha256 = hashlib.sha256(document.text.encode()).hexdigest()
        resume.page_count = document.page_count

        user_settings = SettingsRepository(self._session).get_for_user(resume.user_id)
        consent = bool(user_settings and user_settings.llm_consent)
        outcome = self._ai.extract(resume.user_id, document.text, consent=consent)
        extraction = outcome.extraction or heuristic_extract(document.text)
        method = "llm" if outcome.extraction else "heuristic"

        data = EvidenceValidator(document.text, self._today).validate(extraction)
        current = self._profiles.current(resume.user_id)
        self._profiles.create_version(
            resume.user_id,
            data=data,
            preferences=preferences_of(current),
            origin="parsed",
            parse_method=method,
            resume_id=resume.id,
            today=self._today,
        )
        resume.status = "parsed"
        resume.parse_notice = outcome.notice
        resume.parsed_at = datetime.now(UTC)
        self._session.commit()
        logger.info(
            "resume_profile_created",
            extra={"resume_id": str(resume.id), "method": method, "cached": outcome.from_cache,
                   "skills": len(data.skills), "experience": len(data.experience),
                   "unsupported_claims": len(data.unsupported)},
        )  # fmt: skip
