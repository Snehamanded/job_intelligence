import logging
import time

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window counter in Redis. Fails open if Redis is unavailable."""

    def __init__(self, redis: Redis, *, scope: str, limit: int, window_seconds: int) -> None:
        self._redis = redis
        self._scope = scope
        self._limit = limit
        self._window = window_seconds

    def hit(self, identity: str) -> int | None:
        """Record a hit. Returns seconds until retry if the limit is exceeded, else None."""
        window_index = int(time.time()) // self._window
        key = f"rl:{self._scope}:{identity}:{window_index}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window, nx=True)
            count = int(pipe.execute()[0])
        except RedisError:
            logger.warning("rate_limiter_unavailable", extra={"scope": self._scope})
            return None
        if count > self._limit:
            return self._window - int(time.time()) % self._window
        return None
