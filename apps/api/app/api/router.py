from fastapi import APIRouter, Depends

from app.api.deps import verify_csrf
from app.api.routes import (
    account,
    auth,
    cover_letters,
    crm,
    health,
    jobs,
    profile,
    resumes,
    settings,
    tailoring,
)

api_router = APIRouter(prefix="/api", dependencies=[Depends(verify_csrf)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(settings.router)
api_router.include_router(account.router)
api_router.include_router(resumes.router)
api_router.include_router(profile.router)
api_router.include_router(jobs.router)
api_router.include_router(crm.router)
api_router.include_router(tailoring.router)
api_router.include_router(cover_letters.router)
