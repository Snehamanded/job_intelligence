import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.ai.providers import get_ai_provider
from app.api.deps import AppSettings, CurrentUser, DbSession, Queue, ai_rate_limit
from app.models import CoverLetter
from app.schemas.cover_letters import (
    CoverLetterCreate,
    CoverLetterDetail,
    CoverLetterSave,
    CoverLetterSummary,
    SentencesUpdate,
)
from app.schemas.errors import ErrorResponse
from app.services.cover_letters.service import CoverLetterError, CoverLetterService

router = APIRouter(tags=["cover-letters"])
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _service(db: DbSession, user: CurrentUser, settings: AppSettings) -> CoverLetterService:
    return CoverLetterService(db, user.id, get_ai_provider(settings), settings)


Service = Depends(_service)


def _own(service: CoverLetterService, letter_id: uuid.UUID) -> CoverLetter:
    letter = service.get(letter_id)
    if letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cover letter not found")
    return letter


def _detail(service: CoverLetterService, letter: CoverLetter) -> CoverLetterDetail:
    ready = letter.status in ("ready", "saved")
    content = service.content(letter) if ready else None
    return CoverLetterDetail.model_validate(
        {
            **CoverLetterSummary.model_validate(letter).model_dump(),
            "paragraphs": service.paragraphs(letter),
            "preview": service.preview(letter) if ready else [],
            "signature": content.signature if content else None,
        }
    )


def _raise(exc: CoverLetterError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.post(
    "/cover-letters",
    response_model=CoverLetterDetail,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(ai_rate_limit)],
    responses=ERRORS,
)
def create_cover_letter(
    body: CoverLetterCreate, user: CurrentUser, queue: Queue, service: CoverLetterService = Service
) -> CoverLetterDetail:
    try:
        letter = service.create(body)
    except CoverLetterError as exc:
        raise _raise(exc) from exc
    queue.enqueue_cover_letter(user.id, letter.id)
    return _detail(service, service.get(letter.id) or letter)


@router.get("/cover-letters", response_model=list[CoverLetterSummary])
def list_cover_letters(
    job_id: uuid.UUID | None = None, service: CoverLetterService = Service
) -> list[CoverLetterSummary]:
    return [CoverLetterSummary.model_validate(c) for c in service.all(job_id)]


@router.get("/cover-letters/{letter_id}", response_model=CoverLetterDetail, responses=ERRORS)
def get_cover_letter(
    letter_id: uuid.UUID, service: CoverLetterService = Service
) -> CoverLetterDetail:
    return _detail(service, _own(service, letter_id))


@router.patch(
    "/cover-letters/{letter_id}/sentences", response_model=CoverLetterDetail, responses=ERRORS
)
def update_sentences(
    letter_id: uuid.UUID, body: SentencesUpdate, service: CoverLetterService = Service
) -> CoverLetterDetail:
    letter = _own(service, letter_id)
    try:
        service.update(letter, body)
    except CoverLetterError as exc:
        raise _raise(exc) from exc
    return _detail(service, letter)


@router.post("/cover-letters/{letter_id}/save", response_model=CoverLetterDetail, responses=ERRORS)
def save_cover_letter(
    letter_id: uuid.UUID, body: CoverLetterSave, service: CoverLetterService = Service
) -> CoverLetterDetail:
    letter = _own(service, letter_id)
    try:
        service.save(letter, body.name)
    except CoverLetterError as exc:
        raise _raise(exc) from exc
    return _detail(service, letter)


@router.delete(
    "/cover-letters/{letter_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS
)
def delete_cover_letter(letter_id: uuid.UUID, service: CoverLetterService = Service) -> None:
    service.delete(_own(service, letter_id))


@router.get(
    "/cover-letters/{letter_id}/docx",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            }
        },
        **ERRORS,
    },
)
def download_cover_letter(letter_id: uuid.UUID, service: CoverLetterService = Service) -> Response:
    letter = _own(service, letter_id)
    if letter.status != "saved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Save this letter before downloading it.")
    filename = re.sub(r"[^A-Za-z0-9]+", "-", letter.name).strip("-")[:80] or "cover-letter"
    return Response(
        content=service.render_docx(letter),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.docx"',
            "Cache-Control": "private, no-store",
        },
    )
