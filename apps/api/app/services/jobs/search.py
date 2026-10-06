import logging
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, FetchReport, JobConnector, SearchQuery
from app.models import JobSourceConfig, SearchRun
from app.services.jobs.normalize import normalize, title_matches
from app.services.jobs.store import JobStore

logger = logging.getLogger(__name__)

_COUNTER = {"new": "new", "updated": "updated", "duplicate": "duplicates"}


class SearchService:
    def __init__(self, session: Session, connectors: list[JobConnector]) -> None:
        self._session = session
        self._connectors = connectors

    def run(self, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
        run = self._session.scalar(
            select(SearchRun).where(SearchRun.id == run_id, SearchRun.user_id == user_id)
        )
        if run is None:
            return
        run.status, run.started_at = "running", datetime.now(UTC)
        self._session.commit()
        logger.info(
            "search_started", extra={"search_run_id": str(run.id), "keywords": len(run.keywords)}
        )

        targets: dict[str, list[str]] = defaultdict(list)
        for config in self._session.scalars(
            select(JobSourceConfig).where(
                JobSourceConfig.user_id == user_id, JobSourceConfig.enabled.is_(True)
            )
        ):
            targets[config.source].append(config.identifier)

        results: list[dict[str, Any]] = []
        for connector in self._connectors:
            if connector.needs_targets and not targets.get(connector.name):
                results.append({"source": connector.name, "label": connector.label,
                                "status": "skipped", "error": "Not configured"})  # fmt: skip
                continue
            results.append(self._run_connector(user_id, run, connector, targets[connector.name]))
            # Persist progress per source, so one bad source can't lose the others' results.
            run.source_results = list(results)
            self._session.commit()

        run.source_results = results
        ran = [r for r in results if r["status"] != "skipped"]
        run.status = "failed" if ran and all(r["status"] == "failed" for r in ran) else "completed"
        if not ran:
            run.error_message = "No sources are configured. Add a Greenhouse board first."
        run.finished_at = datetime.now(UTC)
        self._session.commit()
        logger.info(
            "search_completed",
            extra={"search_run_id": str(run.id), "status": run.status,
                   "new": sum(r.get("new", 0) for r in results)},
        )  # fmt: skip

    def _run_connector(
        self, user_id: uuid.UUID, run: SearchRun, connector: JobConnector, targets: list[str]
    ) -> dict[str, Any]:
        started = time.perf_counter()
        report = FetchReport()
        counts = {"fetched": 0, "kept": 0, "new": 0, "updated": 0, "duplicates": 0}
        store = JobStore(self._session, user_id)
        status, error = "completed", None
        try:
            for posting in connector.fetch(SearchQuery(run.keywords, targets), report):
                counts["fetched"] += 1
                if not title_matches(posting.title, run.keywords):
                    continue
                counts["kept"] += 1
                outcome = store.save(normalize(posting)).outcome
                counts[
                    "new"
                    if outcome == "new"
                    else "updated"
                    if outcome == "updated"
                    else "duplicates"
                ] += 1
            self._session.commit()
        except ConnectorError as exc:
            self._session.rollback()
            status, error = "failed", str(exc)
        except Exception:
            # Any connector bug is contained: the search continues with the other sources.
            self._session.rollback()
            logger.exception("source_crashed", extra={"source": connector.name})
            status, error = "failed", "Unexpected error while reading this source"
        if status == "completed" and report.errors:
            status, error = "partial", "; ".join(report.errors)[:500]
        duration_ms = round((time.perf_counter() - started) * 1000)
        event = "source_failed" if status == "failed" else "source_completed"
        base = {"search_run_id": str(run.id), "source": connector.name}
        logger.info(event, extra={**base, "status": status, "duration_ms": duration_ms, **counts})
        if counts["duplicates"]:
            logger.info("duplicates_removed", extra={**base, "count": counts["duplicates"]})
        return {"source": connector.name, "label": connector.label, "status": status,
                "error": error, "duration_ms": duration_ms, "is_mock": connector.is_mock,
                **counts}  # fmt: skip
