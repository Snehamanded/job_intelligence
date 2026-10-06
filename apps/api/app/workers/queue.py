import uuid
from typing import Protocol

from redis import Redis
from rq import Queue

from app.core.config import Settings

QUEUE_NAME = "default"


class TaskQueue(Protocol):
    def enqueue_parse(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> None: ...

    def enqueue_search(self, user_id: uuid.UUID, run_id: uuid.UUID) -> None: ...

    def enqueue_rescore(self, user_id: uuid.UUID) -> None: ...

    def enqueue_import(self, user_id: uuid.UUID, batch_id: uuid.UUID) -> None: ...

    def enqueue_tailor(self, user_id: uuid.UUID, version_id: uuid.UUID) -> None: ...

    def enqueue_cover_letter(self, user_id: uuid.UUID, letter_id: uuid.UUID) -> None: ...


class RQTaskQueue:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._queue = Queue(QUEUE_NAME, connection=redis)
        self._settings = settings

    def enqueue_parse(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        from app.workers.tasks import parse_resume_job

        self._queue.enqueue(
            parse_resume_job,
            str(user_id),
            str(resume_id),
            job_timeout=self._settings.parse_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )

    def enqueue_search(self, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
        from app.workers.tasks import run_search_job

        self._queue.enqueue(
            run_search_job,
            str(user_id),
            str(run_id),
            job_timeout=self._settings.search_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )

    def enqueue_import(self, user_id: uuid.UUID, batch_id: uuid.UUID) -> None:
        from app.workers.tasks import import_posts_job

        self._queue.enqueue(
            import_posts_job,
            str(user_id),
            str(batch_id),
            job_timeout=self._settings.search_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )

    def enqueue_rescore(self, user_id: uuid.UUID) -> None:
        from app.workers.tasks import rescore_matches_job

        self._queue.enqueue(
            rescore_matches_job,
            str(user_id),
            job_timeout=self._settings.search_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )

    def enqueue_tailor(self, user_id: uuid.UUID, version_id: uuid.UUID) -> None:
        from app.workers.tasks import tailor_resume_job

        self._queue.enqueue(
            tailor_resume_job,
            str(user_id),
            str(version_id),
            job_timeout=self._settings.parse_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )

    def enqueue_cover_letter(self, user_id: uuid.UUID, letter_id: uuid.UUID) -> None:
        from app.workers.tasks import cover_letter_job

        self._queue.enqueue(
            cover_letter_job,
            str(user_id),
            str(letter_id),
            job_timeout=self._settings.parse_job_timeout_seconds,
            failure_ttl=7 * 24 * 3600,
        )
