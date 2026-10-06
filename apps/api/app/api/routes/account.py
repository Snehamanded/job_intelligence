from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import AppSettings, CurrentUser, DbSession, Storage, auth_rate_limit
from app.api.routes.auth import clear_session
from app.schemas.errors import ErrorResponse
from app.services.account import AccountService

router = APIRouter(tags=["account"])


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@router.get("/me/export", response_model=dict[str, Any])
def export_my_data(
    user: CurrentUser, db: DbSession, storage: Storage, response: Response
) -> dict[str, Any]:
    response.headers["Content-Disposition"] = 'attachment; filename="my-data.json"'
    response.headers["Cache-Control"] = "private, no-store"
    return AccountService(db, storage).export(user)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth_rate_limit)],
    responses={403: {"model": ErrorResponse}},
)
def delete_my_account(
    body: DeleteAccountRequest,
    user: CurrentUser,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    response: Response,
) -> None:
    if not AccountService(db, storage).delete(user, body.password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")
    clear_session(response, settings)
