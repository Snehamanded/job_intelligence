import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, ApplicationNote, Interview, Job
from app.schemas.crm import (
    Analytics,
    ApplicationCreate,
    ApplicationUpdate,
    GroupRates,
    InterviewCreate,
    InterviewUpdate,
    Rates,
    WeekCount,
)
from app.services.jobs.listing import JobListingService

logger = logging.getLogger(__name__)

# Progress order for the funnel. Rejected/withdrawn are outcomes, not progress.
PROGRESS = {"saved": 0, "applied": 1, "interviewing": 2, "offer": 3}
CLOSED = {"rejected", "withdrawn"}


class CRMError(Exception):
    """Message is safe to show the user."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


class ApplicationService:
    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    # --- reads ---------------------------------------------------------------------------

    def get(self, application_id: uuid.UUID) -> Application | None:
        return self._session.scalar(
            select(Application).where(
                Application.id == application_id, Application.user_id == self._user_id
            )
        )

    def all(self) -> list[Application]:
        return list(
            self._session.scalars(
                select(Application)
                .where(Application.user_id == self._user_id)
                .order_by(Application.stage, Application.position, Application.updated_at.desc())
            )
        )

    def next_interviews(self) -> dict[uuid.UUID, datetime]:
        rows = self._session.execute(
            select(Interview.application_id, func.min(Interview.scheduled_at))
            .where(
                Interview.user_id == self._user_id,
                Interview.outcome == "pending",
                Interview.scheduled_at >= datetime.now(UTC),
            )
            .group_by(Interview.application_id)
        )
        return {app_id: at for app_id, at in rows}

    def note_counts(self) -> dict[uuid.UUID, int]:
        rows = self._session.execute(
            select(ApplicationNote.application_id, func.count())
            .where(ApplicationNote.user_id == self._user_id)
            .group_by(ApplicationNote.application_id)
        )
        return {app_id: n for app_id, n in rows}

    def by_job(self, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, Application]:
        if not job_ids:
            return {}
        rows = self._session.scalars(
            select(Application).where(
                Application.user_id == self._user_id, Application.job_id.in_(job_ids)
            )
        )
        return {a.job_id: a for a in rows if a.job_id}

    def events(self, application_id: uuid.UUID) -> list[ApplicationEvent]:
        return list(
            self._session.scalars(
                select(ApplicationEvent)
                .where(
                    ApplicationEvent.application_id == application_id,
                    ApplicationEvent.user_id == self._user_id,
                )
                .order_by(ApplicationEvent.created_at)
            )
        )

    # --- writes --------------------------------------------------------------------------

    def _event(
        self,
        app: Application,
        kind: str,
        *,
        from_stage: str | None = None,
        to_stage: str | None = None,
        detail: str | None = None,
    ) -> None:
        self._session.add(
            ApplicationEvent(
                user_id=self._user_id, application_id=app.id, kind=kind,
                from_stage=from_stage, to_stage=to_stage, detail=detail,
            )
        )  # fmt: skip

    def create(self, body: ApplicationCreate) -> Application:
        if body.job_id is not None:
            job = self._session.scalar(
                select(Job).where(Job.id == body.job_id, Job.user_id == self._user_id)
            )
            if job is None:
                raise CRMError("Job not found", 404)
            match = (
                JobListingService(self._session, self._user_id)
                .current_matches([job.id])
                .get(job.id)
            )
            app = Application(
                user_id=self._user_id, job_id=job.id, title=job.title, company=job.company,
                location=" · ".join(job.locations) or None, url=job.url, source=job.source,
                match_score=match.match_score if match else None,
                match_label=match.label if match else None,
            )  # fmt: skip
        else:
            app = Application(
                user_id=self._user_id, job_id=None, title=" ".join((body.title or "").split()),
                company=" ".join((body.company or "").split()), location=body.location,
                url=body.url, source="external",
            )  # fmt: skip
        app.stage = body.stage
        app.position = 0
        if body.stage not in ("saved",) and body.stage not in CLOSED:
            app.applied_at = body.applied_at or date.today()
        elif body.applied_at:
            app.applied_at = body.applied_at
        if body.stage in CLOSED:
            app.closed_at = datetime.now(UTC)
        self._session.add(app)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise CRMError("This job is already in your applications.", 409) from exc
        self._event(app, "created", to_stage=app.stage)
        self._session.commit()
        logger.info(
            "application_created", extra={"application_id": str(app.id), "stage": app.stage}
        )
        return app

    def move(self, app: Application, stage: str, detail: str | None = None) -> None:
        if stage == app.stage:
            return
        previous = app.stage
        app.stage = stage
        if PROGRESS.get(stage, 0) >= 1 and app.applied_at is None:
            app.applied_at = date.today()
        app.closed_at = datetime.now(UTC) if stage in CLOSED else None
        self._event(app, "stage_changed", from_stage=previous, to_stage=stage, detail=detail)
        logger.info("application_stage_changed", extra={"application_id": str(app.id),
                    "from_stage": previous, "to_stage": stage})  # fmt: skip

    def update(self, app: Application, body: ApplicationUpdate) -> Application:
        fields = body.model_fields_set
        if body.stage is not None:
            self.move(app, body.stage)
        if "position" in fields and body.position is not None:
            app.position = body.position
        if "applied_at" in fields:
            app.applied_at = body.applied_at
        if "next_action" in fields:
            app.next_action = body.next_action.strip() if body.next_action else None
        if "next_action_date" in fields:
            app.next_action_date = body.next_action_date
        self._session.commit()
        return app

    def delete(self, app: Application) -> None:
        self._session.delete(app)
        self._session.commit()

    # --- notes ---------------------------------------------------------------------------

    def notes(self, app: Application) -> list[ApplicationNote]:
        return list(
            self._session.scalars(
                select(ApplicationNote)
                .where(
                    ApplicationNote.application_id == app.id,
                    ApplicationNote.user_id == self._user_id,
                )
                .order_by(ApplicationNote.created_at.desc())
            )
        )

    def add_note(self, app: Application, body: str) -> ApplicationNote:
        note = ApplicationNote(user_id=self._user_id, application_id=app.id, body=body.strip())
        self._session.add(note)
        app.updated_at = datetime.now(UTC)
        self._session.commit()
        return note

    def get_note(self, note_id: uuid.UUID) -> ApplicationNote | None:
        return self._session.scalar(
            select(ApplicationNote).where(
                ApplicationNote.id == note_id, ApplicationNote.user_id == self._user_id
            )
        )

    # --- interviews ----------------------------------------------------------------------

    def interviews(self, app: Application) -> list[Interview]:
        return list(
            self._session.scalars(
                select(Interview)
                .where(Interview.application_id == app.id, Interview.user_id == self._user_id)
                .order_by(Interview.scheduled_at)
            )
        )

    def add_interview(self, app: Application, body: InterviewCreate) -> Interview:
        interview = Interview(
            user_id=self._user_id, application_id=app.id, scheduled_at=body.scheduled_at,
            kind=body.kind, location=body.location, notes=body.notes, outcome="pending",
            checklist=[item.model_dump() for item in body.checklist],
        )  # fmt: skip
        self._session.add(interview)
        self._event(app, "interview_added", detail=body.kind.replace("_", " "))
        if app.stage in ("saved", "applied"):
            self.move(app, "interviewing", detail="Interview scheduled")
        self._session.commit()
        return interview

    def get_interview(self, interview_id: uuid.UUID) -> Interview | None:
        return self._session.scalar(
            select(Interview).where(
                Interview.id == interview_id, Interview.user_id == self._user_id
            )
        )

    def update_interview(self, interview: Interview, body: InterviewUpdate) -> Interview:
        for field in body.model_fields_set:
            value = getattr(body, field)
            if field == "checklist":
                value = [item.model_dump() for item in body.checklist or []]
            elif value is None and field in ("scheduled_at", "kind", "outcome"):
                continue
            setattr(interview, field, value)
        if "outcome" in body.model_fields_set and body.outcome and body.outcome != "pending":
            app = self.get(interview.application_id)
            if app:
                self._event(app, "interview_outcome", detail=body.outcome)
        self._session.commit()
        return interview

    def upcoming(self, days: int = 14) -> list[tuple[Interview, Application]]:
        now = datetime.now(UTC)
        rows = self._session.execute(
            select(Interview, Application)
            .join(Application, Application.id == Interview.application_id)
            .where(
                Interview.user_id == self._user_id,
                Interview.outcome == "pending",
                Interview.scheduled_at >= now,
                Interview.scheduled_at <= now + timedelta(days=days),
            )
            .order_by(Interview.scheduled_at)
            .limit(20)
        )
        return [(i, a) for i, a in rows]

    # --- analytics -----------------------------------------------------------------------

    def analytics(self, today: date | None = None) -> Analytics:
        apps = self.all()
        reached: dict[uuid.UUID, int] = {a.id: PROGRESS.get(a.stage, 0) for a in apps}
        events = self._session.scalars(
            select(ApplicationEvent).where(ApplicationEvent.user_id == self._user_id)
        )
        for e in events:
            for stage in (e.from_stage, e.to_stage):
                if stage in PROGRESS and e.application_id in reached:
                    reached[e.application_id] = max(reached[e.application_id], PROGRESS[stage])

        def rates(group: list[Application]) -> dict[str, Any]:
            applied = [a for a in group if a.applied_at is not None or reached[a.id] >= 1]
            interviews = [a for a in applied if reached[a.id] >= 2]
            offers = [a for a in applied if reached[a.id] >= 3]
            responded = [a for a in applied if reached[a.id] >= 2 or a.stage == "rejected"]
            n = len(applied)

            def ratio(k: int) -> float | None:
                return round(k / n, 3) if n else None

            return {
                "applied": n, "responded": len(responded), "interviews": len(interviews),
                "offers": len(offers), "response_rate": ratio(len(responded)),
                "interview_rate": ratio(len(interviews)), "offer_rate": ratio(len(offers)),
            }  # fmt: skip

        def grouped(key: Callable[[Application], str]) -> list[GroupRates]:
            groups: dict[str, list[Application]] = defaultdict(list)
            for a in apps:
                groups[key(a)].append(a)
            result = [GroupRates(group=g, **rates(items)) for g, items in groups.items()]
            return sorted(result, key=lambda r: (-r.applied, r.group))

        stage_counts = {
            s: 0 for s in ("saved", "applied", "interviewing", "offer", "rejected", "withdrawn")
        }
        for a in apps:
            stage_counts[a.stage] += 1
        funnel = {
            s: sum(1 for a in apps if reached[a.id] >= level) for s, level in PROGRESS.items()
        }

        today = today or date.today()
        this_week = today - timedelta(days=today.weekday())
        weeks = [this_week - timedelta(weeks=i) for i in range(11, -1, -1)]
        counts: dict[date, int] = defaultdict(int)
        for a in apps:
            if a.applied_at:
                counts[a.applied_at - timedelta(days=a.applied_at.weekday())] += 1
        return Analytics(
            stage_counts=stage_counts,
            funnel=funnel,
            overall=Rates(**rates(apps)),
            by_source=grouped(lambda a: a.source),
            by_match_band=grouped(lambda a: a.match_label or "Not scored"),
            weekly=[WeekCount(week_start=w, applied=counts[w]) for w in weeks],
        )
