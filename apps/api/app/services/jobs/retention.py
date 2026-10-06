"""Deletes stale data so the database stays small (free hosting tiers have ~0.5 GB).

Only jobs the user hasn't acted on are removed: never one with an application, a tailored resume
or a cover letter. Off unless JOB_RETENTION_DAYS is set.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    Application,
    CoverLetter,
    Embedding,
    ImportBatch,
    Job,
    ResumeVersion,
    SearchRun,
)

logger = logging.getLogger(__name__)


def prune(session: Session, settings: Settings, user_id: uuid.UUID) -> int:
    """Delete this user's stale jobs and old bookkeeping. Returns the number of jobs deleted."""
    days = settings.job_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    in_use = [
        select(model.job_id).where(model.user_id == user_id, model.job_id.is_not(None))
        for model in (Application, ResumeVersion, CoverLetter)
    ]
    deleted = session.execute(
        delete(Job)
        .where(Job.user_id == user_id, Job.last_seen_at < cutoff,
               *(Job.id.not_in(q) for q in in_use))
        .returning(Job.id)
    ).all()  # fmt: skip
    # Job embeddings are keyed by text, not job: drop old ones; live jobs get re-embedded once.
    session.execute(
        delete(Embedding).where(
            Embedding.user_id == user_id, Embedding.kind == "job", Embedding.created_at < cutoff
        )
    )
    for model in (SearchRun, ImportBatch):
        session.execute(delete(model).where(model.user_id == user_id, model.created_at < cutoff))
    session.commit()
    if deleted:
        logger.info("stale_jobs_deleted", extra={"user_id": str(user_id), "jobs": len(deleted)})
    return len(deleted)


__all__ = ["prune"]
