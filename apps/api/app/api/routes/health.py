import logging

from fastapi import APIRouter, Response, status
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession, RedisClient
from app.schemas.health import CheckStatus, HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health(db: DbSession, redis: RedisClient, response: Response) -> HealthResponse:
    database: CheckStatus = "ok"
    redis_status: CheckStatus = "ok"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("health_database_failed")
        database = "error"
    try:
        redis.ping()
    except RedisError:
        logger.exception("health_redis_failed")
        redis_status = "error"
    healthy = database == "ok" and redis_status == "ok"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if healthy else "degraded", database=database, redis=redis_status
    )
