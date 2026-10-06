from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from app.connectors.base import ConnectorError, FetchReport, SearchQuery, Tier
from app.connectors.mock import MockConnector
from app.services.jobs.normalize import RawPosting
from tests.conftest import InlineQueue, register

PREFS = {
    "remote_scope": "india",
    "onsite_locations": ["Bangalore"],
    "open_to": ["full_time", "internship"],
    "target_roles": [],
}


class BrokenConnector:
    name, label, is_mock, needs_targets = "broken", "Broken", False, False
    tier: Tier = "A"

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        raise ConnectorError("Source is down")
        yield  # pragma: no cover


class CrashingConnector:
    name, label, is_mock, needs_targets = "crashing", "Crashing", False, False
    tier: Tier = "B"

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        yield RawPosting("crashing", "1", "Backend Engineer", "X", "Pune", "text")
        raise RuntimeError("bug in connector")


def _prefs(client: TestClient, headers: dict[str, str], **extra: Any) -> None:
    resp = client.put(
        "/api/profile", json={"data": {}, "preferences": {**PREFS, **extra}}, headers=headers
    )
    assert resp.status_code == 200, resp.text


def _add_board(client: TestClient, headers: dict[str, str], token: str) -> Any:
    return client.post(
        "/api/job-sources", json={"source": "greenhouse", "identifier": token}, headers=headers
    )


def _search(client: TestClient, headers: dict[str, str], keywords: list[str] | None = None) -> Any:
    body = {} if keywords is None else {"keywords": keywords}
    resp = client.post("/api/searches", json=body, headers=headers)
    assert resp.status_code == 202, resp.text
    return client.get(f"/api/searches/{resp.json()['id']}").json()


def test_board_validation(client: TestClient) -> None:
    headers = register(client)
    added = _add_board(client, headers, " Groww ")
    assert added.status_code == 201
    assert added.json()["display_name"] == "Groww"
    assert _add_board(client, headers, "groww").status_code == 422  # duplicate
    missing = _add_board(client, headers, "nosuchboard")
    assert missing.status_code == 422 and "Board not found" in missing.json()["detail"]
    assert _add_board(client, headers, "../x").status_code == 422
    assert [s["identifier"] for s in client.get("/api/job-sources").json()] == ["groww"]


def test_search_without_sources(client: TestClient) -> None:
    headers = register(client)
    run = _search(client, headers)
    assert run["status"] == "completed"
    assert run["source_results"][0]["status"] == "skipped"
    assert "Add a Greenhouse board" in run["error_message"]


def test_search_real_payloads_with_eligibility(client: TestClient) -> None:
    headers = register(client)
    _prefs(client, headers)
    _add_board(client, headers, "groww")
    _add_board(client, headers, "gitlab")

    run = _search(client, headers)
    assert run["status"] == "completed"
    gh = run["source_results"][0]
    assert (gh["source"], gh["status"], gh["fetched"], gh["kept"], gh["new"]) == (
        "greenhouse",
        "completed",
        6,
        6,
        6,
    )

    eligible = client.get("/api/jobs").json()
    everything = client.get("/api/jobs", params={"eligible_only": False}).json()
    assert everything["total"] == 6
    assert eligible["total"] + eligible["hidden_ineligible"] == 6
    titles = {j["title"] for j in eligible["items"]}
    assert "Video Editor Intern" in titles  # Bengaluru, internship allowed
    assert "AI Transformation Owner, CRO" not in titles  # remote, US only

    us = next(j for j in everything["items"] if j["title"] == "AI Transformation Owner, CRO")
    location = next(c for c in us["eligibility"]["checks"] if c["name"] == "location")
    assert location == {
        "name": "location",
        "status": "fail",
        "reason": "Remote only in United States",
    }
    assert us["salary_currency"] == "USD" and us["salary_unknown"] is False

    detail = client.get(f"/api/jobs/{us['id']}").json()
    assert "Salary Range" in detail["description_text"]

    # Running again updates in place instead of duplicating.
    again = _search(client, headers)["source_results"][0]
    assert (again["new"], again["updated"]) == (0, 6)
    assert client.get("/api/jobs", params={"eligible_only": False}).json()["total"] == 6


def test_keywords_filter_titles(client: TestClient) -> None:
    headers = register(client)
    _add_board(client, headers, "groww")
    _prefs(client, headers, target_roles=["Video Editor"])
    run = _search(client, headers)  # defaults to target roles
    assert run["keywords"] == ["Video Editor"]
    assert run["source_results"][0]["kept"] == 1
    run = _search(client, headers, ["Relationship Manager", "Internal Audit"])
    assert run["source_results"][0]["kept"] == 2


def test_failing_connectors_do_not_break_search(client: TestClient, queue: InlineQueue) -> None:
    headers = register(client)
    _add_board(client, headers, "groww")
    queue.connectors = [BrokenConnector(), CrashingConnector(), *queue.connectors]
    run = _search(client, headers)
    statuses = {r["source"]: (r["status"], r["error"]) for r in run["source_results"]}
    assert statuses["broken"] == ("failed", "Source is down")
    assert statuses["crashing"] == ("failed", "Unexpected error while reading this source")
    assert statuses["greenhouse"][0] == "completed"
    assert run["status"] == "completed"
    jobs = client.get("/api/jobs", params={"eligible_only": False}).json()
    assert {j["source"] for j in jobs["items"]} == {"greenhouse"}  # crashed source rolled back


def test_cross_source_duplicates_collapse(client: TestClient, queue: InlineQueue) -> None:
    headers = register(client)
    queue.connectors = [MockConnector("linkedin", "LinkedIn"), MockConnector("naukri", "Naukri")]
    run = _search(client, headers)
    by_source = {r["source"]: r for r in run["source_results"]}
    assert by_source["linkedin"]["new"] == 2
    assert (by_source["naukri"]["new"], by_source["naukri"]["duplicates"]) == (1, 1)
    jobs = client.get("/api/jobs", params={"eligible_only": False}).json()["items"]
    backend = next(j for j in jobs if j["title"] == "Backend Engineer")
    assert backend["source"] == "linkedin"
    assert [s["source"] for s in backend["also_seen_on"]] == ["naukri"]
    assert all(j["is_mock"] for j in jobs)


def test_manual_import_text_and_greenhouse_url(client: TestClient) -> None:
    headers = register(client)
    text = client.post(
        "/api/jobs/import",
        json={
            "title": "Python Developer",
            "company": "Example Corp",
            "location": "Bangalore, India",
            "description": "We need a Python developer with 2+ years of experience. "
            "CTC: 10-14 LPA. This is a full-time role.",
        },
        headers=headers,
    )
    assert text.status_code == 201, text.text
    body = text.json()
    assert (body["source"], body["employment_type"], body["experience_min_years"]) == (
        "manual",
        "full_time",
        2,
    )
    assert (body["salary_min"], body["salary_max"], body["salary_currency"]) == (
        1000000,
        1400000,
        "INR",
    )
    assert body["locations"] == ["Bengaluru, India"]

    import json

    from tests.conftest import GREENHOUSE_FIXTURES

    job_id = json.loads((GREENHOUSE_FIXTURES / "groww_jobs.json").read_text())["jobs"][0]["id"]
    url = client.post(
        "/api/jobs/import",
        json={"url": f"https://job-boards.eu.greenhouse.io/groww/jobs/{job_id}"},
        headers=headers,
    )
    assert url.status_code == 201, url.text
    assert url.json()["company"] == "Groww"

    bad = client.post(
        "/api/jobs/import", json={"url": "https://www.linkedin.com/jobs/view/1"}, headers=headers
    )
    assert bad.status_code == 422 and "Paste the job description" in bad.json()["detail"]
    short = client.post(
        "/api/jobs/import",
        json={"title": "x", "company": "y", "description": "too short"},
        headers=headers,
    )
    assert short.status_code == 422


def test_jobs_are_private_per_user(client: TestClient) -> None:
    headers = register(client, email="a@example.com")
    _add_board(client, headers, "groww")
    _search(client, headers)
    job_id = client.get("/api/jobs", params={"eligible_only": False}).json()["items"][0]["id"]
    run_id = client.get("/api/searches").json()[0]["id"]
    source_id = client.get("/api/job-sources").json()[0]["id"]
    client.post("/api/auth/logout", headers=headers)

    other = register(client, email="b@example.com")
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.delete(f"/api/jobs/{job_id}", headers=other).status_code == 404
    assert client.get(f"/api/searches/{run_id}").status_code == 404
    assert client.delete(f"/api/job-sources/{source_id}", headers=other).status_code == 404
    assert client.get("/api/jobs", params={"eligible_only": False}).json()["total"] == 0


def test_connectors_listing(client: TestClient) -> None:
    register(client)
    connectors = {c["name"]: c for c in client.get("/api/connectors").json()}
    assert connectors["greenhouse"]["kind"] == "real"
    assert connectors["linkedin"] == {
        **connectors["linkedin"],
        "tier": "C",
        "kind": "mock",
        "enabled": False,
    }
