import logging
import uuid
from datetime import UTC, date, datetime

from rq.timeouts import JobTimeoutException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ai.providers import AIProvider, get_ai_provider
from app.connectors.base import JobConnector
from app.connectors.registry import build_connectors
from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.models import SearchRun
from app.services.cover_letters.service import CoverLetterService
from app.services.jobs.search import SearchService
from app.services.matching.service import MatchingService
from app.services.resume.parsing import ResumeParsingService
from app.services.storage import LocalFileStorage, get_storage
from app.services.tailoring.service import TailoringService

logger = logging.getLogger(__name__)

TIMEOUT_MESSAGE = "Reading this resume took too long. Try a simpler or smaller file."


def rescore(
    session: Session, provider: AIProvider | None, settings: Settings, user_id: uuid.UUID
) -> None:
    """Scoring problems never fail the parse or search that triggered them."""
    try:
        MatchingService(session, provider, settings).rescore(user_id)
    except Exception:
        session.rollback()
        logger.exception("matching_failed", extra={"user_id": str(user_id)})


def parse_and_score(
    session: Session,
    *,
    provider: AIProvider | None,
    settings: Settings,
    storage: LocalFileStorage,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    today: date | None = None,
) -> None:
    service = ResumeParsingService(
        session, provider=provider, settings=settings, storage=storage, today=today
    )
    try:
        service.parse(user_id, resume_id)
    except JobTimeoutException:
        session.rollback()
        logger.warning("resume_parse_timeout", extra={"resume_id": str(resume_id)})
        service.mark_failed(user_id, resume_id, TIMEOUT_MESSAGE)
        return
    rescore(session, provider, settings, user_id)


def search_and_score(
    session: Session,
    *,
    connectors: list[JobConnector],
    provider: AIProvider | None,
    settings: Settings,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    try:
        SearchService(session, connectors).run(user_id, run_id)
    except Exception as exc:
        session.rollback()
        timed_out = isinstance(exc, JobTimeoutException)
        logger.exception("search_failed", extra={"search_run_id": str(run_id)})
        session.execute(
            update(SearchRun)
            .where(SearchRun.id == run_id, SearchRun.user_id == user_id)
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                error_message="The search took too long." if timed_out else "The search failed.",
            )
        )
        session.commit()
        if not timed_out:
            raise
        return
    rescore(session, provider, settings, user_id)


# RQ entry points: plain arguments only.


def parse_resume_job(user_id: str, resume_id: str) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        parse_and_score(
            session,
            provider=get_ai_provider(settings),
            settings=settings,
            storage=get_storage(settings),
            user_id=uuid.UUID(user_id),
            resume_id=uuid.UUID(resume_id),
        )


def run_search_job(user_id: str, run_id: str) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        search_and_score(
            session,
            connectors=build_connectors(settings),
            provider=get_ai_provider(settings),
            settings=settings,
            user_id=uuid.UUID(user_id),
            run_id=uuid.UUID(run_id),
        )


def rescore_matches_job(user_id: str) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        rescore(session, get_ai_provider(settings), settings, uuid.UUID(user_id))


def tailor(
    session: Session,
    provider: AIProvider | None,
    settings: Settings,
    user_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    service = TailoringService(session, user_id, provider, settings)
    try:
        service.generate(version_id)
    except Exception:
        session.rollback()
        logger.exception("tailoring_failed", extra={"version_id": str(version_id)})
        version = service.get(version_id)
        if version is not None:
            version.status, version.notice = "failed", "Generating suggestions failed. Try again."
            session.commit()


def tailor_resume_job(user_id: str, version_id: str) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        tailor(
            session, get_ai_provider(settings), settings, uuid.UUID(user_id), uuid.UUID(version_id)
        )


def write_cover_letter(
    session: Session,
    provider: AIProvider | None,
    settings: Settings,
    user_id: uuid.UUID,
    letter_id: uuid.UUID,
) -> None:
    service = CoverLetterService(session, user_id, provider, settings)
    try:
        service.generate(letter_id)
    except Exception:
        session.rollback()
        logger.exception("cover_letter_failed", extra={"letter_id": str(letter_id)})
        letter = service.get(letter_id)
        if letter is not None:
            letter.status, letter.notice = "failed", "Writing the letter failed. Try again."
            session.commit()


def cover_letter_job(user_id: str, letter_id: str) -> None:
    settings = get_settings()
    with get_sessionmaker()() as session:
        write_cover_letter(
            session, get_ai_provider(settings), settings, uuid.UUID(user_id), uuid.UUID(letter_id)
        )
