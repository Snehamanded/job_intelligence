import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from app.api.deps import AppSettings, CurrentUser, DbSession, Queue, Storage, ai_rate_limit
from app.models import Resume
from app.schemas.errors import ErrorResponse
from app.schemas.resume import ResumeRead
from app.services.resume.documents import MEDIA_TYPES, UploadRejectedError
from app.services.resumes import ResumeService

router = APIRouter(tags=["resumes"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


def _service(db: DbSession, settings: AppSettings, storage: Storage, queue: Queue) -> ResumeService:
    return ResumeService(db, settings, storage, queue)


Service = Depends(_service)


def _own(service: ResumeService, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
    resume = service.get(user_id, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(ai_rate_limit)],
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
)
async def upload_resume(
    file: UploadFile, user: CurrentUser, settings: AppSettings, service: ResumeService = Service
) -> ResumeRead:
    # Read one byte past the limit so oversize files are rejected without reading them fully.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"The file is larger than {limit_mb:g} MB."
        )
    try:
        resume = service.upload(user.id, file.filename, data)
    except UploadRejectedError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    return ResumeRead.model_validate(resume)


@router.get("/resumes", response_model=list[ResumeRead])
def list_resumes(user: CurrentUser, service: ResumeService = Service) -> list[ResumeRead]:
    return [ResumeRead.model_validate(r) for r in service.list(user.id)]


@router.get("/resumes/{resume_id}", response_model=ResumeRead, responses=NOT_FOUND)
def get_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeService = Service
) -> ResumeRead:
    return ResumeRead.model_validate(_own(service, user.id, resume_id))


@router.get(
    "/resumes/{resume_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}, **NOT_FOUND},
)
def download_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeService = Service
) -> Response:
    resume = _own(service, user.id, resume_id)
    return Response(
        content=service.read_file(resume),
        media_type=MEDIA_TYPES[resume.file_type],  # type: ignore[index]
        headers={
            "Content-Disposition": f'attachment; filename="resume.{resume.file_type}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/resumes/{resume_id}/reparse",
    response_model=ResumeRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(ai_rate_limit)],
    responses={**NOT_FOUND, 409: {"model": ErrorResponse}},
)
def reparse_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeService = Service
) -> ResumeRead:
    resume = _own(service, user.id, resume_id)
    if resume.status in ("queued", "parsing"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This resume is already being parsed.")
    return ResumeRead.model_validate(service.reparse(resume))


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeService = Service
) -> None:
    service.delete(_own(service, user.id, resume_id))
