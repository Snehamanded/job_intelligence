"""Settings and storage used by the free-tier deployment (docs/DEPLOYMENT.md)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.api.deps import get_file_storage
from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.models import Application, Job, StoredFile
from app.services.jobs.retention import prune
from app.services.storage import DatabaseFileStorage
from tests.conftest import InlineQueue, csrf, register, upload
from tests.helpers import fixture_text

SECRET = "x" * 40


def test_signup_allowlist(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "allowed_signup_emails", "Me@Example.com, other@x.io")
    stranger = client.post("/api/auth/register", headers=csrf(client),
                           json={"email": "stranger@example.com", "password": "correct-horse-1"})  # fmt: skip
    assert stranger.status_code == 403
    register(client, email="me@example.com")  # case-insensitive match


def test_production_refuses_unsafe_settings() -> None:
    base = {"database_url": "postgresql://u:p@h/d", "jwt_secret": SECRET,
            "environment": "production"}  # fmt: skip
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(**base, cookie_secure=False, allow_registration=True, allowed_signup_emails="")  # type: ignore[arg-type]
    open_signup = Settings(**base, cookie_secure=True, allowed_signup_emails="")  # type: ignore[arg-type]
    assert open_signup.signup_allowed("anyone@example.com")
    ok = Settings(**base, cookie_secure=True, allowed_signup_emails="me@example.com")  # type: ignore[arg-type]
    assert ok.signup_allowed("ME@example.com") and not ok.signup_allowed("x@example.com")
    assert Settings(**base, cookie_secure=True, allow_registration=False)  # type: ignore[arg-type]


def test_uploads_can_live_in_the_database(
    app: FastAPI, client: TestClient, queue: InlineQueue
) -> None:
    storage = DatabaseFileStorage()
    app.dependency_overrides[get_file_storage] = lambda: storage
    queue.storage = storage
    headers = register(client)
    resume = upload(client, headers, "resume.txt", fixture_text("sneha_backend.txt").encode())
    assert client.get(f"/api/resumes/{resume['id']}").json()["status"] == "parsed"
    with get_sessionmaker()() as session:
        assert session.scalar(select(func.count()).select_from(StoredFile)) == 1
    assert client.delete(f"/api/resumes/{resume['id']}", headers=headers).status_code == 204
    with get_sessionmaker()() as session:
        assert session.scalar(select(func.count()).select_from(StoredFile)) == 0
    with pytest.raises(FileNotFoundError):
        storage.read(f"{uuid.uuid4()}/missing.pdf")


def test_retention_deletes_only_stale_untouched_jobs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = register(client)
    body = {"title": "Backend Engineer", "company": "Acme", "location": "Bengaluru, India",
            "description": "Build REST APIs in Python and FastAPI. " * 3}  # fmt: skip
    stale = client.post("/api/jobs/import", json=body, headers=headers).json()["id"]
    applied = client.post("/api/jobs/import", json={**body, "company": "Beta", "description": "Beta: " + body["description"]},
                          headers=headers).json()["id"]  # fmt: skip
    fresh = client.post("/api/jobs/import", json={**body, "company": "Gamma", "description": "Gamma: " + body["description"]},
                        headers=headers).json()["id"]  # fmt: skip
    assert client.post("/api/applications", json={"job_id": applied},
                       headers=headers).status_code == 201  # fmt: skip
    old = datetime.now(UTC) - timedelta(days=90)
    with get_sessionmaker()() as session:
        aged = [uuid.UUID(stale), uuid.UUID(applied)]
        session.execute(update(Job).where(Job.id.in_(aged)).values(last_seen_at=old))
        session.commit()
        user_id = session.scalar(select(Job.user_id).where(Job.id == fresh))
        assert user_id is not None
        settings = get_settings()
        assert prune(session, settings, user_id) == 0  # off by default
        monkeypatch.setattr(settings, "job_retention_days", 45)
        assert prune(session, settings, user_id) == 1
        remaining = set(session.scalars(select(Job.id).where(Job.user_id == user_id)))
        assert remaining == {uuid.UUID(applied), uuid.UUID(fresh)}
        assert session.scalar(select(func.count()).select_from(Application)) == 1


def test_wrong_redis_url_fails_with_a_clear_message() -> None:
    with pytest.raises(ValidationError, match="Connect section"):
        Settings(database_url="postgresql://u:p@h/d", jwt_secret=SECRET,
                 redis_url="https://eu1-example.upstash.io")  # fmt: skip
    ok = Settings(database_url="postgresql://u:p@h/d", jwt_secret=SECRET,
                  redis_url=" rediss://default:pw@example.upstash.io:6379 ")  # fmt: skip
    assert ok.redis_url == "rediss://default:pw@example.upstash.io:6379"
