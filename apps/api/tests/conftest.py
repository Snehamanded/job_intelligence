import os
from collections.abc import Iterator
from pathlib import Path

# Must run before the app (and its cached settings) is imported.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://jobcrm:jobcrm@localhost:5433/jobcrm_test"
)
# Tests truncate tables, so refuse to run against anything but a dedicated test database.
_test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if not _test_db_name.endswith("_test"):
    raise RuntimeError(f"TEST_DATABASE_URL must point at a *_test database, got {_test_db_name}")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32
os.environ["AUTH_RATE_LIMIT"] = "5"
os.environ["COOKIE_SECURE"] = "false"
os.environ["LLM_RETRY_BACKOFF_SECONDS"] = "0"
os.environ["AI_PROVIDER"] = "gemini"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import json
import uuid
from datetime import date

import fakeredis
import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.ai.providers.fake import FakeAIProvider
from app.api.deps import get_file_storage, get_greenhouse, get_task_queue
from app.connectors.base import JobConnector
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.http import make_client
from app.core.config import Settings, get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.redis import get_redis
from app.main import create_app
from app.services.storage import LocalFileStorage
from app.workers.tasks import (
    parse_and_score,
    rescore,
    search_and_score,
    tailor,
    write_cover_letter,
)

TODAY = date(2026, 10, 5)

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))


@pytest.fixture
def redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


GREENHOUSE_FIXTURES = Path(__file__).parent / "fixtures" / "greenhouse"


def greenhouse_transport(
    fail_boards: frozenset[str] = frozenset(), requests: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    """Serves recorded Greenhouse responses. Any unknown board is a 404. No network."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        parts = request.url.path.strip("/").split("/")  # v1/boards/{token}[/jobs[/{id}]]
        token = parts[2] if len(parts) > 2 else ""
        if token in fail_boards:
            return httpx.Response(500)
        if len(parts) == 3:
            path = GREENHOUSE_FIXTURES / f"{token}_board.json"
        else:
            path = GREENHOUSE_FIXTURES / f"{token}_jobs.json"
        if not path.exists():
            return httpx.Response(404, json={"status": 404, "error": "Job not found"})
        data = json.loads(path.read_text())
        if len(parts) == 5:
            job = next((j for j in data["jobs"] if str(j["id"]) == parts[4]), None)
            return httpx.Response(200, json=job) if job else httpx.Response(404)
        return httpx.Response(200, json=data)

    return httpx.MockTransport(handler)


def fake_greenhouse(transport: httpx.MockTransport | None = None) -> GreenhouseConnector:
    return GreenhouseConnector(
        make_client(get_settings(), transport or greenhouse_transport()),
        delay_seconds=0,
        sleep=lambda _: None,
    )


class InlineQueue:
    """Runs background jobs immediately, in-process, with fakes for AI and job sources."""

    def __init__(self, provider: FakeAIProvider, settings: Settings, storage: LocalFileStorage):
        self.provider = provider
        self.settings = settings
        self.storage = storage
        self.paused = False
        self.pending: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.connectors: list[JobConnector] = [fake_greenhouse()]
        self.rescores = 0

    def enqueue_search(self, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
        if self.paused:
            self.pending.append((user_id, run_id))
            return
        with get_sessionmaker()() as session:
            search_and_score(
                session,
                connectors=self.connectors,
                provider=self.provider,
                settings=self.settings,
                user_id=user_id,
                run_id=run_id,
            )

    def enqueue_tailor(self, user_id: uuid.UUID, version_id: uuid.UUID) -> None:
        if self.paused:
            return
        with get_sessionmaker()() as session:
            tailor(session, self.provider, self.settings, user_id, version_id)

    def enqueue_cover_letter(self, user_id: uuid.UUID, letter_id: uuid.UUID) -> None:
        if self.paused:
            return
        with get_sessionmaker()() as session:
            write_cover_letter(session, self.provider, self.settings, user_id, letter_id)

    def enqueue_rescore(self, user_id: uuid.UUID) -> None:
        self.rescores += 1
        if self.paused:
            return
        with get_sessionmaker()() as session:
            rescore(session, self.provider, self.settings, user_id)

    def enqueue_parse(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        if self.paused:
            self.pending.append((user_id, resume_id))
            return
        with get_sessionmaker()() as session:
            parse_and_score(
                session,
                provider=self.provider,
                settings=self.settings,
                storage=self.storage,
                user_id=user_id,
                resume_id=resume_id,
                today=TODAY,
            )


@pytest.fixture
def fake_ai() -> FakeAIProvider:
    return FakeAIProvider()


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path / "storage")


@pytest.fixture
def queue(fake_ai: FakeAIProvider, storage: LocalFileStorage) -> InlineQueue:
    return InlineQueue(fake_ai, get_settings(), storage)


@pytest.fixture
def app(redis: fakeredis.FakeRedis, storage: LocalFileStorage, queue: InlineQueue) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_redis] = lambda: redis
    application.dependency_overrides[get_file_storage] = lambda: storage
    application.dependency_overrides[get_task_queue] = lambda: queue
    application.dependency_overrides[get_greenhouse] = lambda: fake_greenhouse()
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def csrf(client: TestClient) -> dict[str, str]:
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def register(
    client: TestClient, email: str = "sneha@example.com", password: str = "correct-horse-1"
) -> dict[str, str]:
    """Register and return headers carrying the session's CSRF token."""
    resp = client.post(
        "/api/auth/register", json={"email": email, "password": password}, headers=csrf(client)
    )
    assert resp.status_code == 201, resp.text
    return {"X-CSRF-Token": resp.json()["csrf_token"]}


def give_consent(client: TestClient, headers: dict[str, str]) -> None:
    assert (
        client.put("/api/settings", json={"llm_consent": True}, headers=headers).status_code == 200
    )


def upload(
    client: TestClient, headers: dict[str, str], filename: str, data: bytes
) -> dict[str, object]:
    resp = client.post("/api/resumes", files={"file": (filename, data)}, headers=headers)
    assert resp.status_code == 202, resp.text
    body: dict[str, object] = resp.json()
    return body


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any real outbound HTTP from a test is a bug: fail loudly."""

    def blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network access is disabled in tests; use httpx.MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
