from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.models import Application, ApplicationEvent, ApplicationNote, Interview
from tests.conftest import InlineQueue, register

DESCRIPTION = (
    "Build Python services with FastAPI and PostgreSQL. 1-3 years of experience. Full-time role."
)


def import_job(client: TestClient, headers: dict[str, str], title: str = "Backend Engineer") -> str:
    resp = client.post(
        "/api/jobs/import",
        json={"title": title, "company": "Acme", "location": "Bengaluru, India",
              "description": DESCRIPTION, "url": "https://example.com/job"},
        headers=headers,
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    job_id: str = resp.json()["id"]
    return job_id


def create(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    resp = client.post("/api/applications", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def patch(client: TestClient, headers: dict[str, str], app_id: str, **body: Any) -> dict[str, Any]:
    resp = client.patch(f"/api/applications/{app_id}", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    return data


def test_track_job_snapshot_and_one_per_job(client: TestClient) -> None:
    headers = register(client)
    job_id = import_job(client, headers)
    app = create(client, headers, job_id=job_id)
    assert (app["title"], app["company"], app["source"], app["stage"]) == (
        "Backend Engineer", "Acme", "manual", "saved"
    )  # fmt: skip
    assert app["url"] == "https://example.com/job"
    assert [e["kind"] for e in app["events"]] == ["created"]

    dup = client.post("/api/applications", json={"job_id": job_id}, headers=headers)
    assert dup.status_code == 409

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["application"] == {"id": app["id"], "stage": "saved"}


def test_external_application_validation(client: TestClient) -> None:
    headers = register(client)
    assert client.post("/api/applications", json={"title": "X"}, headers=headers).status_code == 422
    bad_url = {"title": "Dev", "company": "Co", "url": "javascript:alert(1)"}
    assert client.post("/api/applications", json=bad_url, headers=headers).status_code == 422
    app = create(
        client, headers, title="  Data   Engineer ", company="Elsewhere Ltd", stage="applied"
    )
    assert (app["title"], app["source"], app["stage"]) == ("Data Engineer", "external", "applied")
    assert app["applied_at"] == date.today().isoformat()


def test_stage_rules_and_history(client: TestClient) -> None:
    headers = register(client)
    app = create(client, headers, title="Dev", company="Co")
    assert app["applied_at"] is None

    app = patch(client, headers, app["id"], stage="applied")
    assert app["applied_at"] == date.today().isoformat()
    app = patch(client, headers, app["id"], stage="rejected")
    assert app["closed_at"] is not None
    app = patch(client, headers, app["id"], stage="applied")  # reopened
    assert app["closed_at"] is None
    app = patch(client, headers, app["id"], applied_at="2026-09-01", next_action="Follow up",
                next_action_date="2026-10-10", position=3)  # fmt: skip
    assert (app["applied_at"], app["next_action"], app["position"]) == (
        "2026-09-01",
        "Follow up",
        3,
    )
    moves = [
        (e["from_stage"], e["to_stage"]) for e in app["events"] if e["kind"] == "stage_changed"
    ]
    assert moves == [("saved", "applied"), ("applied", "rejected"), ("rejected", "applied")]
    assert client.patch(f"/api/applications/{app['id']}", json={"stage": "hired"},
                        headers=headers).status_code == 422  # fmt: skip


def test_notes(client: TestClient) -> None:
    headers = register(client)
    app = create(client, headers, title="Dev", company="Co")
    note = client.post(f"/api/applications/{app['id']}/notes", json={"body": " Called recruiter "},
                       headers=headers).json()  # fmt: skip
    assert note["body"] == "Called recruiter"
    edited = client.patch(
        f"/api/notes/{note['id']}", json={"body": "Called recruiter twice"}, headers=headers
    )
    assert edited.json()["body"] == "Called recruiter twice"
    assert client.get("/api/applications").json()[0]["notes_count"] == 1
    assert client.post(f"/api/applications/{app['id']}/notes", json={"body": ""},
                       headers=headers).status_code == 422  # fmt: skip
    assert client.delete(f"/api/notes/{note['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/applications/{app['id']}").json()["notes"] == []


def test_interviews_move_stage_and_upcoming(client: TestClient) -> None:
    headers = register(client)
    app = create(client, headers, title="Dev", company="Co", stage="applied")
    when = (datetime.now(UTC) + timedelta(days=2)).replace(microsecond=0)
    resp = client.post(
        f"/api/applications/{app['id']}/interviews",
        json={"scheduled_at": when.isoformat(), "kind": "technical", "location": "https://meet.example",
              "checklist": [{"text": "Review system design"}, {"text": "Prepare questions"}]},
        headers=headers,
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    interview = resp.json()
    assert interview["checklist"] == [
        {"text": "Review system design", "done": False}, {"text": "Prepare questions", "done": False}
    ]  # fmt: skip

    detail = client.get(f"/api/applications/{app['id']}").json()
    assert detail["stage"] == "interviewing"  # adding an interview moved it
    assert detail["next_interview_at"] is not None
    assert [e["kind"] for e in detail["events"]][-2:] == ["interview_added", "stage_changed"]

    upcoming = client.get("/api/interviews/upcoming").json()
    assert [(u["title"], u["kind"]) for u in upcoming] == [("Dev", "technical")]

    checklist = [
        {"text": "Review system design", "done": True},
        {"text": "Prepare questions", "done": False},
    ]
    updated = client.patch(f"/api/interviews/{interview['id']}",
                           json={"checklist": checklist, "outcome": "passed"}, headers=headers).json()  # fmt: skip
    assert updated["checklist"][0]["done"] is True and updated["outcome"] == "passed"
    assert client.get("/api/interviews/upcoming").json() == []  # only pending ones are upcoming

    naive = client.post(f"/api/applications/{app['id']}/interviews",
                        json={"scheduled_at": "2026-10-10T10:00:00"}, headers=headers)  # fmt: skip
    assert naive.status_code == 422
    assert client.delete(f"/api/interviews/{interview['id']}", headers=headers).status_code == 204


def test_analytics_on_known_dataset(client: TestClient) -> None:
    headers = register(client)
    # 5 applications: saved only; applied (no reply); applied -> rejected;
    # applied -> interviewing -> rejected; applied -> interviewing -> offer.
    create(client, headers, title="A", company="Co")
    create(client, headers, title="B", company="Co", stage="applied")
    c = create(client, headers, title="C", company="Co", stage="applied")
    patch(client, headers, c["id"], stage="rejected")
    d = create(client, headers, title="D", company="Co", stage="applied")
    patch(client, headers, d["id"], stage="interviewing")
    patch(client, headers, d["id"], stage="rejected")
    e = create(client, headers, title="E", company="Co", stage="applied")
    patch(client, headers, e["id"], stage="interviewing")
    patch(client, headers, e["id"], stage="offer")

    data = client.get("/api/analytics").json()
    assert data["stage_counts"] == {"saved": 1, "applied": 1, "interviewing": 0, "offer": 1,
                                    "rejected": 2, "withdrawn": 0}  # fmt: skip
    assert data["funnel"] == {"saved": 5, "applied": 4, "interviewing": 2, "offer": 1}
    overall = data["overall"]
    assert (overall["applied"], overall["responded"], overall["interviews"], overall["offers"]) == (
        4,
        3,
        2,
        1,
    )
    assert (overall["response_rate"], overall["interview_rate"], overall["offer_rate"]) == (
        0.75,
        0.5,
        0.25,
    )
    assert data["by_source"][0]["group"] == "external"
    assert data["by_match_band"][0]["group"] == "Not scored"
    assert len(data["weekly"]) == 12 and data["weekly"][-1]["applied"] == 4


def test_application_survives_job_deletion(client: TestClient) -> None:
    headers = register(client)
    job_id = import_job(client, headers)
    app = create(client, headers, job_id=job_id)
    assert client.delete(f"/api/jobs/{job_id}", headers=headers).status_code == 204
    kept = client.get(f"/api/applications/{app['id']}").json()
    assert (kept["job_id"], kept["title"]) == (None, "Backend Engineer")


def test_match_snapshot_when_scored(client: TestClient, queue: InlineQueue) -> None:
    headers = register(client)
    client.put("/api/profile", json={"data": {}, "preferences": {"target_roles": ["Backend Engineer"]}},
               headers=headers)  # fmt: skip
    job_id = import_job(client, headers)  # import triggers scoring
    app = create(client, headers, job_id=job_id)
    assert app["match_score"] is not None and app["match_label"] is not None


def test_crm_is_private_exported_and_deleted(client: TestClient) -> None:
    headers = register(client, email="a@example.com")
    app = create(client, headers, title="Dev", company="Co", stage="applied")
    client.post(f"/api/applications/{app['id']}/notes", json={"body": "secret"}, headers=headers)
    exported = client.get("/api/me/export").json()["applications"]
    assert exported[0]["title"] == "Dev" and exported[0]["notes"][0]["body"] == "secret"
    assert exported[0]["history"][0]["kind"] == "created"
    client.post("/api/auth/logout", headers=headers)

    other = register(client, email="b@example.com")
    assert client.get(f"/api/applications/{app['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/applications/{app['id']}", json={"stage": "offer"}, headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/applications/{app['id']}/notes", json={"body": "x"}, headers=other
        ).status_code
        == 404
    )
    assert client.get("/api/applications").json() == []
    assert client.get("/api/analytics").json()["overall"]["applied"] == 0
    client.post("/api/auth/logout", headers=other)

    from app.core.db import get_engine  # noqa: F401  (ensures engine is initialized)

    resp = client.post("/api/auth/login", json={"email": "a@example.com", "password": "correct-horse-1"},
                       headers={"X-CSRF-Token": client.get("/api/auth/csrf").json()["csrf_token"]})  # fmt: skip
    headers = {"X-CSRF-Token": resp.json()["csrf_token"]}
    client.request("DELETE", "/api/me", json={"password": "correct-horse-1"}, headers=headers)
    with get_sessionmaker()() as session:
        for model in (Application, ApplicationEvent, ApplicationNote, Interview):
            assert session.scalar(select(func.count()).select_from(model)) == 0
