import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models import Application
from app.schemas.crm import (
    Analytics,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
    EventRead,
    InterviewCreate,
    InterviewRead,
    InterviewUpdate,
    NoteCreate,
    NoteRead,
    UpcomingInterview,
)
from app.schemas.errors import ErrorResponse
from app.services.crm import ApplicationService, CRMError

router = APIRouter(tags=["applications"])
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}
}  # fmt: skip


def _own(service: ApplicationService, application_id: uuid.UUID) -> Application:
    app = service.get(application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


def _detail(service: ApplicationService, app: Application) -> ApplicationDetail:
    return ApplicationDetail.model_validate(
        {
            **ApplicationSummary.model_validate(app).model_dump(
                exclude={"next_interview_at", "notes_count"}
            ),
            "next_interview_at": service.next_interviews().get(app.id),
            "notes_count": len(notes := service.notes(app)),
            "notes": [NoteRead.model_validate(n) for n in notes],
            "interviews": [InterviewRead.model_validate(i) for i in service.interviews(app)],
            "events": [EventRead.model_validate(e) for e in service.events(app.id)],
        }
    )


@router.get("/applications", response_model=list[ApplicationSummary])
def list_applications(user: CurrentUser, db: DbSession) -> list[ApplicationSummary]:
    service = ApplicationService(db, user.id)
    upcoming, notes = service.next_interviews(), service.note_counts()
    return [
        ApplicationSummary.model_validate(a).model_copy(
            update={"next_interview_at": upcoming.get(a.id), "notes_count": notes.get(a.id, 0)}
        )
        for a in service.all()
    ]


@router.post(
    "/applications", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)  # fmt: skip
def create_application(
    body: ApplicationCreate, user: CurrentUser, db: DbSession
) -> ApplicationDetail:
    service = ApplicationService(db, user.id)
    try:
        app = service.create(body)
    except CRMError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return _detail(service, app)


@router.get("/applications/{application_id}", response_model=ApplicationDetail, responses=ERRORS)
def get_application(
    application_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ApplicationDetail:
    service = ApplicationService(db, user.id)
    return _detail(service, _own(service, application_id))


@router.patch("/applications/{application_id}", response_model=ApplicationDetail, responses=ERRORS)
def update_application(
    application_id: uuid.UUID, body: ApplicationUpdate, user: CurrentUser, db: DbSession
) -> ApplicationDetail:
    service = ApplicationService(db, user.id)
    app = service.update(_own(service, application_id), body)
    return _detail(service, app)


@router.delete(
    "/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS
)
def delete_application(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    service = ApplicationService(db, user.id)
    service.delete(_own(service, application_id))


@router.post(
    "/applications/{application_id}/notes", response_model=NoteRead,
    status_code=status.HTTP_201_CREATED, responses=ERRORS,
)  # fmt: skip
def add_note(
    application_id: uuid.UUID, body: NoteCreate, user: CurrentUser, db: DbSession
) -> NoteRead:
    service = ApplicationService(db, user.id)
    return NoteRead.model_validate(service.add_note(_own(service, application_id), body.body))


@router.patch("/notes/{note_id}", response_model=NoteRead, responses=ERRORS)
def update_note(note_id: uuid.UUID, body: NoteCreate, user: CurrentUser, db: DbSession) -> NoteRead:
    service = ApplicationService(db, user.id)
    note = service.get_note(note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    note.body = body.body.strip()
    db.commit()
    return NoteRead.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_note(note_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    note = ApplicationService(db, user.id).get_note(note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    db.delete(note)
    db.commit()


@router.post(
    "/applications/{application_id}/interviews", response_model=InterviewRead,
    status_code=status.HTTP_201_CREATED, responses=ERRORS,
)  # fmt: skip
def add_interview(
    application_id: uuid.UUID, body: InterviewCreate, user: CurrentUser, db: DbSession
) -> InterviewRead:
    service = ApplicationService(db, user.id)
    return InterviewRead.model_validate(service.add_interview(_own(service, application_id), body))


@router.get("/interviews/upcoming", response_model=list[UpcomingInterview])
def upcoming_interviews(user: CurrentUser, db: DbSession) -> list[UpcomingInterview]:
    return [
        UpcomingInterview(
            **InterviewRead.model_validate(i).model_dump(), title=a.title, company=a.company
        )
        for i, a in ApplicationService(db, user.id).upcoming()
    ]


@router.patch("/interviews/{interview_id}", response_model=InterviewRead, responses=ERRORS)
def update_interview(
    interview_id: uuid.UUID, body: InterviewUpdate, user: CurrentUser, db: DbSession
) -> InterviewRead:
    service = ApplicationService(db, user.id)
    interview = service.get_interview(interview_id)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return InterviewRead.model_validate(service.update_interview(interview, body))


@router.delete(
    "/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS
)
def delete_interview(interview_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    interview = ApplicationService(db, user.id).get_interview(interview_id)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    db.delete(interview)
    db.commit()


@router.get("/analytics", response_model=Analytics)
def analytics(user: CurrentUser, db: DbSession) -> Analytics:
    return ApplicationService(db, user.id).analytics()
