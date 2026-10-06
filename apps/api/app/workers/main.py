"""Entry point for the background worker: `python -m app.workers.main`."""

from rq import SimpleWorker, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import get_redis
from app.workers.queue import QUEUE_NAME


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    # SimpleWorker runs jobs in this process instead of forking one per job (job timeouts still
    # apply): less memory, for small hosts that run the API and worker together.
    worker_class = SimpleWorker if settings.worker_no_fork else Worker
    worker_class([QUEUE_NAME], connection=get_redis()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
