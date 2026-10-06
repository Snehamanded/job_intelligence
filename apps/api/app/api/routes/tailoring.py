import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.ai.providers import get_ai_provider
from app.api.deps import AppSettings, CurrentUser, DbSession, Queue, Storage, ai_rate_limit
from app.models import ResumeVersion
from app.schemas.errors import ErrorResponse
from app.schemas.tailoring import (
    DecisionsUpdate,
    TailoringCreate,
    TailoringDetail,
    TailoringSave,
    TailoringSummary,
)
from app.services.tailoring.service import TailoringError, TailoringService

router = APIRouter(tags=["tailoring"])
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _service(
    db: DbSession, user: CurrentUser, settings: AppSettings, storage: Storage
) -> TailoringService:
    return TailoringService(db, user.id, get_ai_provider(settings), settings, storage)


Service = Depends(_service)


def _own(service: TailoringService, version_id: uuid.UUID) -> ResumeVersion:
    version = service.get(version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    return version


def _detail(service: TailoringService, version: ResumeVersion) -> TailoringDetail:
    return TailoringDetail.model_validate(
        {
            **TailoringSummary.model_validate(version).model_dump(),
            "changes": service.changes(version),
            "preview": service.preview(version) if version.status in ("ready", "saved") else None,
            "skill_gaps": service.skill_gaps(version),
        }
    )


@router.post(
    "/tailoring",
    response_model=TailoringDetail,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(ai_rate_limit)],
    responses=ERRORS,
)
def start_tailoring(
    body: TailoringCreate, user: CurrentUser, queue: Queue, service: TailoringService = Service
) -> TailoringDetail:
    try:
        version = service.create(body.job_id)
    except TailoringError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    queue.enqueue_tailor(user.id, version.id)
    refreshed = service.get(version.id)
    return _detail(service, refreshed or version)


@router.get("/tailoring", response_model=list[TailoringSummary])
def list_tailoring(
    job_id: uuid.UUID | None = None, service: TailoringService = Service
) -> list[TailoringSummary]:
    return [TailoringSummary.model_validate(v) for v in service.all(job_id)]


@router.get("/tailoring/{version_id}", response_model=TailoringDetail, responses=ERRORS)
def get_tailoring(version_id: uuid.UUID, service: TailoringService = Service) -> TailoringDetail:
    return _detail(service, _own(service, version_id))


@router.patch("/tailoring/{version_id}/decisions", response_model=TailoringDetail, responses=ERRORS)
def decide(
    version_id: uuid.UUID, body: DecisionsUpdate, service: TailoringService = Service
) -> TailoringDetail:
    version = _own(service, version_id)
    try:
        service.decide(version, dict(body.decisions))
    except TailoringError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return _detail(service, version)


@router.post("/tailoring/{version_id}/save", response_model=TailoringDetail, responses=ERRORS)
def save(
    version_id: uuid.UUID, body: TailoringSave, service: TailoringService = Service
) -> TailoringDetail:
    version = _own(service, version_id)
    try:
        service.save(version, body.name)
    except TailoringError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return _detail(service, version)


@router.delete("/tailoring/{version_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_tailoring(version_id: uuid.UUID, service: TailoringService = Service) -> None:
    service.delete(_own(service, version_id))


@router.get(
    "/tailoring/{version_id}/docx",
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
def download_docx(version_id: uuid.UUID, service: TailoringService = Service) -> Response:
    version = _own(service, version_id)
    if version.status != "saved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Save this version before downloading it.")
    filename = re.sub(r"[^A-Za-z0-9]+", "-", version.name).strip("-")[:80] or "resume"
    return Response(
        content=service.docx(version),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.docx"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/tailoring/{version_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, **ERRORS},
)
def download_pdf(version_id: uuid.UUID, service: TailoringService = Service) -> Response:
    """Built on the server, so there's no browser header or footer; keeps the upload's layout."""
    version = _own(service, version_id)
    if version.status != "saved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Save this version before downloading it.")
    filename = re.sub(r"[^A-Za-z0-9]+", "-", version.name).strip("-")[:80] or "resume"
    return Response(
        content=service.pdf(version),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
