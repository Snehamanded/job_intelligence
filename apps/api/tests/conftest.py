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
from app.api.deps import get_connectors, get_file_storage, get_task_queue
from app.connectors.base import JobConnector
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.registry import Connectors, build
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


SOURCES = Path(__file__).parent / "fixtures" / "sources"
CAREERS = Path(__file__).parent / "fixtures" / "careers"
# Fake DNS for the import tests: public by default, private for these hosts.
PRIVATE_HOSTS = {"localhost": "127.0.0.1", "intranet.example": "10.0.0.5",
                 "metadata.example": "169.254.169.254", "v6local.example": "::1"}  # fmt: skip


def fake_resolve(host: str) -> list[str]:
    return [PRIVATE_HOSTS.get(host, "93.184.216.34")]


def _json(path: Path) -> httpx.Response:
    if not path.exists():
        return httpx.Response(404, json={"error": "not found"})
    return httpx.Response(200, json=json.loads(path.read_text()))


def greenhouse_transport(
    fail_boards: frozenset[str] = frozenset(), requests: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    """Serves recorded responses for every source. Unknown paths are 404. No network."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        host, path = request.url.host, request.url.path
        parts = path.strip("/").split("/")
        if host == "boards-api.greenhouse.io":
            token = parts[2] if len(parts) > 2 else ""
            if token in fail_boards:
                return httpx.Response(500)
            if len(parts) == 3:
                return _json(GREENHOUSE_FIXTURES / f"{token}_board.json")
            fixture = GREENHOUSE_FIXTURES / f"{token}_jobs.json"
            if not fixture.exists():
                return httpx.Response(404, json={"status": 404})
            data = json.loads(fixture.read_text())
            if len(parts) == 5:
                job = next((j for j in data["jobs"] if str(j["id"]) == parts[4]), None)
                return httpx.Response(200, json=job) if job else httpx.Response(404)
            return httpx.Response(200, json=data)
        if host in ("api.lever.co", "api.eu.lever.co"):  # /v0/postings/{site}[/{id}]
            site = parts[2]
            if site in fail_boards:
                return httpx.Response(500)
            fixture = SOURCES / f"lever_{site}.json"
            if not fixture.exists():
                return httpx.Response(404, json={"ok": False})
            postings = json.loads(fixture.read_text())
            if len(parts) == 4:
                p = next((x for x in postings if x["id"] == parts[3]), None)
                return httpx.Response(200, json=p) if p else httpx.Response(404)
            skip = int(request.url.params.get("skip", 0))
            limit = int(request.url.params.get("limit", 1000))
            return httpx.Response(200, json=postings[skip : skip + limit])
        if host == "api.ashbyhq.com":
            return _json(SOURCES / f"ashby_{parts[-1]}.json")
        if host == "remoteok.com" and path == "/api":
            return _json(SOURCES / "remoteok.json")
        if host == "remotive.com" and path == "/api/remote-jobs":
            return _json(SOURCES / "remotive.json")
        if host == "api.adzuna.com":
            return _json(SOURCES / f"adzuna_{parts[3]}.json")
        if host == "careers.example.com":
            if path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
            if path == "/moved":
                return httpx.Response(302, headers={"location": "/jobs/platform"})
            if path == "/to-internal":
                return httpx.Response(302, headers={"location": "http://intranet.example/admin"})
            page = {"/jobs/platform": "job.html", "/jobs/remote": "remote.html",
                    "/about": "none.html", "/private/job": "job.html"}.get(path)  # fmt: skip
            if page:
                return httpx.Response(200, text=(CAREERS / page).read_text(),
                                      headers={"content-type": "text/html; charset=utf-8"})  # fmt: skip
            if path == "/file.pdf":
                return httpx.Response(
                    200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"}
                )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def fake_connectors(transport: httpx.MockTransport | None = None) -> Connectors:
    settings = get_settings().model_copy(update={"connector_request_delay_seconds": 0})
    return build(
        settings, transport or greenhouse_transport(), resolve=fake_resolve, sleep=lambda _: None
    )


def fake_greenhouse(transport: httpx.MockTransport | None = None) -> GreenhouseConnector:
    return fake_connectors(transport).greenhouse


class InlineQueue:
    """Runs background jobs immediately, in-process, with fakes for AI and job sources."""

    def __init__(self, provider: FakeAIProvider, settings: Settings, storage: LocalFileStorage):
        self.provider = provider
        self.settings = settings
        self.storage = storage
        self.paused = False
        self.pending: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.connectors: list[JobConnector] = fake_connectors().for_search(settings)
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
    application.dependency_overrides[get_connectors] = lambda: fake_connectors()
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
