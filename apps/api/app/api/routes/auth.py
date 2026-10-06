from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AppSettings, CurrentUser, DbSession, auth_rate_limit
from app.core.config import Settings
from app.core.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    create_access_token,
    new_csrf_token,
)
from app.models import User
from app.schemas.auth import AuthResponse, CsrfResponse, LoginRequest, RegisterRequest, UserRead
from app.schemas.errors import ErrorResponse
from app.services.auth import AuthService, EmailAlreadyRegisteredError

router = APIRouter(tags=["auth"])


def _set_cookie(response: Response, key: str, value: str, settings: Settings, max_age: int) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _start_session(user: User, response: Response, settings: AppSettings) -> AuthResponse:
    max_age = settings.access_token_ttl_minutes * 60
    _set_cookie(response, ACCESS_COOKIE, create_access_token(user.id, settings), settings, max_age)
    # Rotate the CSRF token whenever the session changes.
    csrf = new_csrf_token()
    _set_cookie(response, CSRF_COOKIE, csrf, settings, max_age)
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf)


@router.get("/auth/csrf", response_model=CsrfResponse)
def get_csrf_token(request: Request, response: Response, settings: AppSettings) -> CsrfResponse:
    token = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    _set_cookie(response, CSRF_COOKIE, token, settings, settings.access_token_ttl_minutes * 60)
    return CsrfResponse(csrf_token=token)


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
    responses={403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def register(
    body: RegisterRequest, response: Response, db: DbSession, settings: AppSettings
) -> AuthResponse:
    if not settings.allow_registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is disabled")
    try:
        user = AuthService(db).register(body.email, body.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered") from exc
    return _start_session(user, response, settings)


@router.post(
    "/auth/login",
    response_model=AuthResponse,
    dependencies=[Depends(auth_rate_limit)],
    responses={401: {"model": ErrorResponse}},
)
def login(
    body: LoginRequest, response: Response, db: DbSession, settings: AppSettings
) -> AuthResponse:
    user = AuthService(db).authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _start_session(user, response, settings)


def clear_session(response: Response, settings: Settings) -> None:
    for key in (ACCESS_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            key, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
        )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: AppSettings) -> None:
    clear_session(response, settings)


@router.get("/me", response_model=UserRead, responses={401: {"model": ErrorResponse}})
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
