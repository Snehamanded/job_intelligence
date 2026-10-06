from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis import Redis
from sqlalchemy.orm import Session

from app.connectors.registry import Connectors, build
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter
from app.core.redis import get_redis
from app.core.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    csrf_tokens_match,
    decode_access_token,
)
from app.models import User
from app.repositories.users import UserRepository
from app.services.storage import FileStorage, get_storage
from app.workers.queue import RQTaskQueue, TaskQueue

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
RedisClient = Annotated[Redis, Depends(get_redis)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_csrf(request: Request) -> None:
    """Double-submit check on every mutating request under /api."""
    if request.method in _SAFE_METHODS:
        return
    if not csrf_tokens_match(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token, settings) if token else None
    user = UserRepository(db).get_by_id(user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def auth_rate_limit(request: Request, redis: RedisClient, settings: AppSettings) -> None:
    limiter = RateLimiter(
        redis,
        scope="auth",
        limit=settings.auth_rate_limit,
        window_seconds=settings.auth_rate_window_seconds,
    )
    client_ip = request.client.host if request.client else "unknown"
    retry_after = limiter.hit(client_ip)
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def ai_rate_limit(user: CurrentUser, redis: RedisClient, settings: AppSettings) -> None:
    """Per-user limit on endpoints that can trigger LLM calls."""
    limiter = RateLimiter(
        redis,
        scope="ai",
        limit=settings.ai_rate_limit,
        window_seconds=settings.ai_rate_window_seconds,
    )
    retry_after = limiter.hit(str(user.id))
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many resume uploads. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def get_file_storage(settings: AppSettings) -> FileStorage:
    return get_storage(settings)


def get_task_queue(redis: RedisClient, settings: AppSettings) -> TaskQueue:
    return RQTaskQueue(redis, settings)


Storage = Annotated[FileStorage, Depends(get_file_storage)]
Queue = Annotated[TaskQueue, Depends(get_task_queue)]


def search_rate_limit(user: CurrentUser, redis: RedisClient, settings: AppSettings) -> None:
    limiter = RateLimiter(
        redis,
        scope="search",
        limit=settings.search_rate_limit,
        window_seconds=settings.search_rate_window_seconds,
    )
    retry_after = limiter.hit(str(user.id))
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many searches. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def get_connectors(settings: AppSettings) -> Connectors:
    return build(settings)


JobConnectors = Annotated[Connectors, Depends(get_connectors)]
