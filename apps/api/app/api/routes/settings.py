from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, Queue
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.settings import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsRead)
def get_settings(user: CurrentUser, db: DbSession) -> SettingsRead:
    return SettingsRead.model_validate(SettingsService(db).get(user.id))


@router.put("/settings", response_model=SettingsRead)
def update_settings(
    body: SettingsUpdate, user: CurrentUser, db: DbSession, queue: Queue
) -> SettingsRead:
    before = SettingsService(db).get(user.id).llm_consent
    updated = SettingsService(db).update(user.id, llm_consent=body.llm_consent)
    if updated.llm_consent != before:
        queue.enqueue_rescore(user.id)  # switches between code-only and AI scoring
    return SettingsRead.model_validate(updated)
