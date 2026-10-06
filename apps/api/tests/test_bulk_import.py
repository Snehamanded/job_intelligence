"""Importing job posts pasted from alert emails or WhatsApp. All content is fictional."""

import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.ai.providers.fake import FakeAIProvider
from app.connectors.safe_http import SafeFetcher, UnsafeURLError
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import ImportBatch, Job, UserSettings
from app.services.jobs.bulk_import import BulkImporter, limit, locate, whatsapp_messages
from app.services.jobs.importer import restricted_site
from tests.conftest import fake_connectors, register

FIXTURES = Path(__file__).parent / "fixtures" / "imports"
ALERT = (FIXTURES / "linkedin_alert.txt").read_text()
CHAT = (FIXTURES / "whatsapp_export.txt").read_text()


def _import(client: TestClient, headers: dict[str, str], channel: str, text: str) -> dict:  # type: ignore[type-arg]
    resp = client.post("/api/job-imports", json={"channel": channel, "text": text},
                       headers=headers)  # fmt: skip
    assert resp.status_code == 202, resp.text
    batch: dict = client.get(f"/api/job-imports/{resp.json()['id']}").json()  # type: ignore[type-arg]
    return batch


def test_whatsapp_export_without_ai(client: TestClient) -> None:
    headers = register(client)
    batch = _import(client, headers, "whatsapp", CHAT)
    assert (batch["status"], batch["method"]) == ("completed", "rules")
    assert "AI processing is off" in batch["notice"]
    posts = {r["title"]: r for r in batch["results"]}
    assert set(posts) == {"Python Developer", "Data Analyst Intern"}  # chatter and media skipped
    assert posts["Python Developer"]["company"] == "Acme Cloudworks"
    assert posts["Data Analyst Intern"]["company"] == "Zentrix Analytics"
    # The careers link has no readable job data (404 here), so the message itself is the posting.
    assert posts["Python Developer"]["status"] == "new"

    job_id = posts["Python Developer"]["job_id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["source"] == "whatsapp" and "Django" in job["description_text"]
    assert job["url"] == "https://careers.acmecloud.example/jobs/python-developer"
    # Sender names, numbers and timestamps never reach the saved posting, and the paste is gone.
    assert "Placement Updates" not in job["description_text"]
    assert "98765" not in json.dumps(client.get("/api/me/export").json()["job_imports"])
    with get_sessionmaker()() as session:
        assert session.scalar(select(ImportBatch.pasted_text)) is None

    again = _import(client, headers, "whatsapp", CHAT)  # importing twice doesn't duplicate jobs
    assert {r["status"] for r in again["results"]} <= {"duplicate", "updated"}


def test_alert_email_without_ai(client: TestClient) -> None:
    headers = register(client)
    batch = _import(client, headers, "email", ALERT)
    posts = {r["title"]: r for r in batch["results"]}
    assert set(posts) == {"Backend Engineer (Python)", "Assistant Manager - Internal Audit",
                          "Junior Data Analyst"}  # fmt: skip
    assert posts["Backend Engineer (Python)"]["company"] == "Finlytic Labs"
    # A company careers (Greenhouse) link is read in full; LinkedIn links are kept, never fetched.
    assert posts["Assistant Manager - Internal Audit"]["status"] == "imported"
    linkedin = posts["Junior Data Analyst"]
    assert linkedin["status"] == "new" and "linkedin.com" in linkedin["url"]
    assert linkedin["note"] and "short summary" in linkedin["note"]
    job = client.get(f"/api/jobs/{linkedin['job_id']}").json()
    assert job["source"] == "email_alert" and job["company"] == "Northwind Retail"


def _consent(user_id: uuid.UUID) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(UserSettings).where(UserSettings.user_id == user_id).values(llm_consent=True)
        )
        session.commit()


def test_ai_posts_are_checked_against_the_pasted_text(client: TestClient) -> None:
    register(client)
    user_id = uuid.UUID(client.get("/api/me").json()["id"])
    _consent(user_id)
    found = {"posts": [
        {"start_quote": "Backend Engineer (Python) Finlytic Labs",
         "end_quote": "jobs/view/4100000001/", "title": "Backend Engineer (Python)",
         "company": "Finlytic Labs", "location": "Bengaluru, Karnataka, India",
         "url": "https://www.linkedin.com/comm/jobs/view/4100000001/"},
        {"start_quote": "Senior Rust Engineer at Finlytic", "end_quote": "apply now",
         "title": "Senior Rust Engineer"},  # invented: its quotes aren't in the text
        {"start_quote": "Junior Data Analyst", "end_quote": "jobs/view/4100000003/",
         "title": "Junior Data Analyst", "company": "Contoso"},  # company not in the post
        {"start_quote": "Junior Data Analyst", "end_quote": "jobs/view/4100000003/",
         "title": "Head of Marketing"},  # title not in the post
    ]}  # fmt: skip
    provider = FakeAIProvider(responses=[json.dumps(found)])
    with get_sessionmaker()() as session:
        batch = ImportBatch(user_id=user_id, channel="email", status="queued", pasted_text=ALERT)
        session.add(batch)
        session.commit()
        BulkImporter(session, provider, get_settings(), fake_connectors(), user_id,
                     sleep=lambda _: None).run(batch.id)  # fmt: skip
        session.refresh(batch)
        assert batch.method == "ai" and batch.pasted_text is None
        results = {r["title"]: r for r in batch.results}
        assert set(results) == {"Backend Engineer (Python)", "Junior Data Analyst"}
        analyst = session.get(Job, uuid.UUID(results["Junior Data Analyst"]["job_id"]))
        assert analyst is not None and analyst.company == "Unknown company"
        assert analyst.description_text.startswith("Junior Data Analyst\nNorthwind Retail")
    # The pasted text went to the model as delimited data.
    assert "<pasted_text>" in provider.calls[0].prompt


def test_whatsapp_formats_and_limits() -> None:
    ios = "[05/10/26, 9:02:11 AM] Jobs Hub: Hiring SDE 1\nApply here\n[05/10/26, 9:03:00 AM] Jobs Hub: Hello"
    assert whatsapp_messages(ios) == ["Hiring SDE 1\nApply here", "Hello"]
    assert whatsapp_messages("Just one pasted message about a job") is None
    assert locate("A  Python\nDeveloper role. Apply soon", "python developer", "apply soon") == (
        3,
        36,
    )
    # Models drop chat formatting marks when quoting.
    assert locate("*Hiring: Python Developer*\nApply", "Hiring: Python Developer Apply", "Apply")
    long_chat = "\n".join(f"05/10/26, 9:{i % 60:02d} am - X: message {i}" for i in range(4000))
    kept, truncated = limit(long_chat, "whatsapp")
    assert truncated and kept.endswith("message 3999") and len(kept) <= 60_000


def test_redirect_to_a_restricted_site_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.host == "lnkd.in":
            return httpx.Response(301, headers={"location": "https://www.linkedin.com/jobs/view/1"})
        raise AssertionError("LinkedIn must not be fetched")

    fetcher = SafeFetcher(httpx.Client(transport=httpx.MockTransport(handler)), user_agent="t",
                          max_bytes=10_000, resolve=lambda _: ["93.184.216.34"])  # fmt: skip
    with pytest.raises(UnsafeURLError, match="LinkedIn"):
        fetcher.fetch_page("https://lnkd.in/abc", refuse=restricted_site)


def test_imports_are_private(client: TestClient) -> None:
    headers = register(client)
    batch = _import(client, headers, "whatsapp", CHAT)
    client.cookies.clear()
    register(client, email="other@example.com")
    assert client.get(f"/api/job-imports/{batch['id']}").status_code == 404
    assert client.get("/api/job-imports").json() == []
