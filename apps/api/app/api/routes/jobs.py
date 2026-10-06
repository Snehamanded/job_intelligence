import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.ai.providers import get_ai_provider
from app.api.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    Greenhouse,
    Queue,
    search_rate_limit,
)
from app.connectors.registry import describe
from app.models import Job, SearchRun
from app.repositories.profiles import ProfileRepository
from app.repositories.settings import SettingsRepository
from app.schemas.errors import ErrorResponse
from app.schemas.jobs import (
    ApplicationRef,
    ConnectorRead,
    EligibilityRead,
    JobDetail,
    JobImportRequest,
    JobListResponse,
    JobSourceCreate,
    JobSourceRead,
    JobSummary,
    SearchRunCreate,
    SearchRunRead,
)
from app.schemas.matching import (
    JobPriorityUpdate,
    MatchDetail,
    MatchStatus,
    MatchSummary,
    ScoringConfigRead,
)
from app.services.job_sources import JobSourceService, SourceConfigError
from app.services.jobs.importer import ImportRejectedError, JobImporter
from app.services.jobs.listing import JobListingService, ListedJob
from app.services.matching.config import ScoringConfigService, ScoringSettings

router = APIRouter(tags=["jobs"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


def _fields(item: ListedJob) -> dict[str, Any]:
    fields = {
        name: getattr(item.job, name)
        for name in JobSummary.model_fields
        if name not in ("eligibility", "match", "application")
    }
    fields["eligibility"] = EligibilityRead.model_validate(item.eligibility, from_attributes=True)
    return fields


def _application(item: ListedJob) -> ApplicationRef | None:
    app = item.application
    return ApplicationRef.model_validate({"id": app.id, "stage": app.stage}) if app else None


def _summary(item: ListedJob) -> JobSummary:
    match = MatchSummary.model_validate(item.match) if item.match else None
    return JobSummary.model_validate(
        {**_fields(item), "match": match, "application": _application(item)}
    )


def _detail(item: ListedJob) -> JobDetail:
    match = MatchDetail.model_validate(item.match, from_attributes=True) if item.match else None
    return JobDetail.model_validate(
        {
            **_fields(item),
            "match": match,
            "application": _application(item),
            "description_text": item.job.description_text,
        }
    )


# --- connectors and sources ---------------------------------------------------------------


@router.get("/connectors", response_model=list[ConnectorRead])
def list_connectors(_: CurrentUser, settings: AppSettings) -> list[ConnectorRead]:
    return [ConnectorRead(**info.__dict__) for info in describe(settings)]


@router.get("/job-sources", response_model=list[JobSourceRead])
def list_job_sources(
    user: CurrentUser, db: DbSession, settings: AppSettings
) -> list[JobSourceRead]:
    return [JobSourceRead.model_validate(c) for c in JobSourceService(db, user.id, settings).list()]


@router.post(
    "/job-sources",
    response_model=JobSourceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(search_rate_limit)],
    responses={422: {"model": ErrorResponse}},
)
def add_job_source(
    body: JobSourceCreate, user: CurrentUser, db: DbSession, settings: AppSettings, gh: Greenhouse
) -> JobSourceRead:
    try:
        config = JobSourceService(db, user.id, settings).add_greenhouse_board(body.board_token, gh)
    except SourceConfigError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return JobSourceRead.model_validate(config)


@router.delete(
    "/job-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND
)
def delete_job_source(
    source_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> None:
    service = JobSourceService(db, user.id, settings)
    config = service.get(source_id)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    service.delete(config)


# --- searches ---------------------------------------------------------------------------


@router.post(
    "/searches",
    response_model=SearchRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(search_rate_limit)],
)
def start_search(
    body: SearchRunCreate, user: CurrentUser, db: DbSession, queue: Queue
) -> SearchRunRead:
    keywords = body.keywords
    if keywords is None:
        profile = ProfileRepository(db).current(user.id)
        keywords = list(profile.target_roles) if profile else []
    keywords = [" ".join(k.split())[:100] for k in keywords if k.strip()][:10]
    run = SearchRun(user_id=user.id, status="queued", keywords=keywords)
    db.add(run)
    db.commit()
    queue.enqueue_search(user.id, run.id)
    db.refresh(run)
    return SearchRunRead.model_validate(run)


@router.get("/searches", response_model=list[SearchRunRead])
def list_searches(user: CurrentUser, db: DbSession) -> list[SearchRunRead]:
    runs = db.scalars(
        select(SearchRun)
        .where(SearchRun.user_id == user.id)
        .order_by(SearchRun.created_at.desc())
        .limit(20)
    )
    return [SearchRunRead.model_validate(r) for r in runs]


@router.get("/searches/{run_id}", response_model=SearchRunRead, responses=NOT_FOUND)
def get_search(run_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SearchRunRead:
    run = db.scalar(select(SearchRun).where(SearchRun.id == run_id, SearchRun.user_id == user.id))
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search not found")
    return SearchRunRead.model_validate(run)


# --- jobs -------------------------------------------------------------------------------


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    user: CurrentUser,
    db: DbSession,
    eligible_only: bool = True,
    high_priority_only: bool = False,
    sort: Literal["rank", "newest"] = "rank",
    source: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    page = JobListingService(db, user.id).list(
        eligible_only=eligible_only,
        high_priority_only=high_priority_only,
        sort=sort,
        source=source,
        q=q,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[_summary(i) for i in page.items],
        total=page.total,
        hidden_ineligible=page.hidden_ineligible,
    )


@router.post(
    "/jobs/import",
    response_model=JobDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(search_rate_limit)],
    responses={422: {"model": ErrorResponse}},
)
def import_job(
    body: JobImportRequest, user: CurrentUser, db: DbSession, gh: Greenhouse, queue: Queue
) -> JobDetail:
    importer = JobImporter(db, user.id, gh)
    try:
        if body.description and body.description.strip():
            job = importer.from_text(
                title=body.title or "",
                company=body.company or "",
                location=body.location or "",
                description=body.description,
                url=body.url,
            )
        else:
            job = importer.from_url(body.url or "")
    except ImportRejectedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    queue.enqueue_rescore(user.id)
    item = JobListingService(db, user.id).get(job.id)
    if item is None:  # just saved; only possible if deleted concurrently
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _detail(item)


@router.get("/jobs/{job_id}", response_model=JobDetail, responses=NOT_FOUND)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobDetail:
    item = JobListingService(db, user.id).get(job_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _detail(item)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    service = JobListingService(db, user.id)
    item = service.get(job_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    service.delete(item.job)


@router.patch("/jobs/{job_id}", response_model=JobDetail, responses=NOT_FOUND)
def update_job_priority(
    job_id: uuid.UUID, body: JobPriorityUpdate, user: CurrentUser, db: DbSession, queue: Queue
) -> JobDetail:
    service = JobListingService(db, user.id)
    item = service.get(job_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    item.job.priority = body.priority
    db.commit()
    queue.enqueue_rescore(user.id)  # priority is part of the rank
    refreshed = service.get(job_id)
    assert refreshed is not None  # noqa: S101 - same transaction, just read
    return _detail(refreshed)


# --- matching ---------------------------------------------------------------------------


@router.get("/scoring-config", response_model=ScoringConfigRead)
def get_scoring_config(user: CurrentUser, db: DbSession) -> ScoringConfigRead:
    version, settings = ScoringConfigService(db, user.id).current()
    db.commit()
    return ScoringConfigRead(version=version, settings=settings)


@router.put("/scoring-config", response_model=ScoringConfigRead)
def update_scoring_config(
    body: ScoringSettings, user: CurrentUser, db: DbSession, queue: Queue
) -> ScoringConfigRead:
    version, settings = ScoringConfigService(db, user.id).update(body)
    db.commit()
    queue.enqueue_rescore(user.id)
    return ScoringConfigRead(version=version, settings=settings)


@router.post(
    "/matches/rescore",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(search_rate_limit)],
)
def rescore_matches(user: CurrentUser, queue: Queue) -> None:
    queue.enqueue_rescore(user.id)


@router.get("/matches/status", response_model=MatchStatus)
def match_status(user: CurrentUser, db: DbSession, settings: AppSettings) -> MatchStatus:
    profile = ProfileRepository(db).current(user.id)
    config_version, _ = ScoringConfigService(db, user.id).current()
    db.commit()
    total = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user.id)) or 0
    scored = len(JobListingService(db, user.id).current_matches()) if profile else 0
    user_settings = SettingsRepository(db).get_for_user(user.id)
    consent = bool(user_settings and user_settings.llm_consent)
    ai_enabled = consent and get_ai_provider(settings) is not None
    note = None
    if profile is None:
        note = "Upload a resume or set preferences to get match scores."
    elif not ai_enabled:
        note = (
            "Scores use code only. Turn on AI processing in Settings for semantic matching."
            if not consent
            else "AI is not configured on this server; scores use code only."
        )
    return MatchStatus(
        profile_version=profile.version if profile else None,
        scoring_config_version=config_version,
        total_jobs=total,
        scored_jobs=scored,
        ai_enabled=ai_enabled,
        note=note,
    )
