from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, Queue
from app.schemas.errors import ErrorResponse
from app.schemas.profile import ProfileRead, ProfileUpdate, ProfileVersionSummary
from app.services.profile import ProfileEditRejectedError, ProfileService, to_read, to_summary

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileRead | None)
def get_profile(user: CurrentUser, db: DbSession) -> ProfileRead | None:
    """The current profile version, or null before the first resume or preferences are saved."""
    profile = ProfileService(db).current(user.id)
    return to_read(profile) if profile else None


@router.get("/profile/versions", response_model=list[ProfileVersionSummary])
def list_profile_versions(user: CurrentUser, db: DbSession) -> list[ProfileVersionSummary]:
    return [to_summary(p) for p in ProfileService(db).versions(user.id)]


@router.put("/profile", response_model=ProfileRead, responses={422: {"model": ErrorResponse}})
def update_profile(
    body: ProfileUpdate, user: CurrentUser, db: DbSession, queue: Queue
) -> ProfileRead:
    """Save edits and preferences as a new version. Resume-sourced items are re-verified."""
    try:
        profile = ProfileService(db).update(user.id, body.data, body.preferences)
    except ProfileEditRejectedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    queue.enqueue_rescore(user.id)  # a new profile version invalidates scores
    return to_read(profile)
