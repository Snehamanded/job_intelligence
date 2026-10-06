"""Entry point for the background worker: `python -m app.workers.main`."""

from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import get_redis
from app.workers.queue import QUEUE_NAME


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    Worker([QUEUE_NAME], connection=get_redis()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
