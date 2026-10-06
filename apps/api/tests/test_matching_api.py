import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.providers.fake import FakeAIProvider
from app.core.db import get_sessionmaker
from app.models import JobMatch
from tests.conftest import InlineQueue, give_consent, register, upload
from tests.helpers import fixture_text

GOLDEN: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "golden" / "jobs.json").read_text()
)
PREFS = {"target_roles": ["Backend Engineer"], "remote_scope": "india",
         "onsite_locations": ["Bengaluru"]}  # fmt: skip


def assessment(**kw: Any) -> str:
    base = {
        "skills": [],
        "project_relevance": 60,
        "relevant_projects": ["Job Tracker"],
        "industry_relevance": 70,
        "explanation": "Good fit for your Python backend work.",
    }
    return json.dumps({**base, **kw})


def setup_user(client: TestClient, queue: InlineQueue) -> dict[str, str]:
    headers = register(client)
    upload(client, headers, "sneha.txt", fixture_text("sneha_backend.txt").encode())
    profile = client.get("/api/profile").json()
    client.put(
        "/api/profile", json={"data": profile["data"], "preferences": PREFS}, headers=headers
    )
    queue.paused = True
    for job in GOLDEN:
        body = {k: job[k] for k in ("title", "company", "location", "description")}
        assert client.post("/api/jobs/import", json=body, headers=headers).status_code == 201
    queue.paused = False
    return headers


def jobs(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(
        "/api/jobs", params={"eligible_only": False, **params}
    ).json()["items"]
    return items


def test_scores_breakdown_and_rank_sorting(client: TestClient, queue: InlineQueue) -> None:
    headers = setup_user(client, queue)
    client.post("/api/matches/rescore", headers=headers)
    items = jobs(client)
    ranks = [j["match"]["rank_score"] for j in items]
    assert ranks == sorted(ranks, reverse=True)
    assert items[0]["title"] == "Backend Engineer (Python)"

    detail = client.get(f"/api/jobs/{items[0]['id']}").json()["match"]
    assert set(detail["components"]) == {
        "skills", "experience", "role", "location", "projects", "industry", "preferences"
    }  # fmt: skip
    assert detail["components"]["skills"]["weight"] == 30
    assert detail["explanation_source"] == "summary"
    skills = {s["name"]: s["status"] for s in detail["skills"]}
    assert skills["Python"] == "demonstrated" and skills["FastAPI"] == "demonstrated"

    status = client.get("/api/matches/status").json()
    assert (status["scored_jobs"], status["total_jobs"], status["ai_enabled"]) == (5, 5, False)
    assert "Turn on AI processing" in status["note"]

    newest = jobs(client, sort="newest")
    assert len(newest) == 5


def test_new_versions_invalidate_scores(client: TestClient, queue: InlineQueue) -> None:
    headers = setup_user(client, queue)
    client.post("/api/matches/rescore", headers=headers)
    before = {j["id"]: j["match"]["match_score"] for j in jobs(client)}
    profile = client.get("/api/profile").json()

    # Skills also come from verified experience bullets, so drop on-site Bengaluru instead:
    # a new profile version where the Bengaluru backend job no longer fits on location.
    prefs = {**PREFS, "onsite_locations": ["Pune"]}
    client.put(
        "/api/profile", json={"data": profile["data"], "preferences": prefs}, headers=headers
    )
    after = jobs(client)
    backend = next(j for j in after if j["title"] == "Backend Engineer (Python)")
    assert backend["match"]["match_score"] < before[backend["id"]]
    assert client.get("/api/matches/status").json()["profile_version"] == profile["version"] + 1

    # A new scoring config version: skills only.
    weights = {"skills": 100, "experience": 0, "role": 0, "location": 0, "projects": 0,
               "industry": 0, "preferences": 0}  # fmt: skip
    resp = client.put("/api/scoring-config", json={"weights": weights}, headers=headers)
    assert resp.status_code == 200 and resp.json()["version"] == 2
    detail = client.get(f"/api/jobs/{backend['id']}").json()["match"]
    assert detail["match_score"] == detail["components"]["skills"]["score"]
    assert detail["scoring_config_version"] == 2

    with get_sessionmaker()() as session:
        versions = session.execute(
            select(
                JobMatch.profile_version, JobMatch.scoring_config_version, func.count()
            ).group_by(JobMatch.profile_version, JobMatch.scoring_config_version)
        ).all()
    assert len(versions) >= 3  # old rows are kept, only current ones are shown

    bad = client.put("/api/scoring-config", json={"ranking": {"match": 2}}, headers=headers)
    assert bad.status_code == 422


def test_ai_path_top_n_and_caches(
    client: TestClient, queue: InlineQueue, fake_ai: FakeAIProvider
) -> None:
    headers = setup_user(client, queue)
    queue.paused = True
    give_consent(client, headers)
    client.put(
        "/api/scoring-config", json={"llm_top_n": 2, "high_priority_threshold": 60}, headers=headers
    )
    queue.paused = False
    fake_ai.responses.extend([
        assessment(skills=[{"name": "Go", "status": "demonstrated", "profile_skill": "Go"}]),
        assessment(),
    ])  # fmt: skip
    client.post("/api/matches/rescore", headers=headers)

    match_calls = [c for c in fake_ai.calls if "job_skills" in c.prompt]
    assert len(match_calls) == 2  # only the top N go to the LLM
    assert "<job_posting>" in match_calls[0].prompt
    eligible = [j for j in jobs(client) if j["eligibility"]["eligible"]]
    # Only eligible jobs (the ones that get ranked) are embedded, once.
    assert fake_ai.embed_calls and len(fake_ai.embed_calls[-1]) == len(eligible) == 2

    items = jobs(client)
    ai_rows = [j for j in items if j["match"]["method"] == "ai"]
    assert len(ai_rows) == 2
    detail = client.get(f"/api/jobs/{ai_rows[0]['id']}").json()["match"]
    assert detail["explanation_source"] == "ai"
    assert detail["components"]["projects"]["method"] == "ai"
    for skill in detail["skills"]:  # the LLM's "Go: demonstrated" claim was not accepted
        if skill["name"] == "Go":
            assert skill["status"] != "demonstrated"
    assert any(j["match"]["high_priority"] for j in items)
    assert jobs(client, high_priority_only=True)

    # Rescoring with the same profile and jobs: no new LLM or embedding calls (cached).
    calls, embeds = len(fake_ai.calls), len(fake_ai.embed_calls)
    client.post("/api/matches/rescore", headers=headers)
    assert len(fake_ai.calls) == calls
    assert all(len(batch) == 0 for batch in fake_ai.embed_calls[embeds:])
    assert [j["match"]["method"] for j in jobs(client)].count("ai") == 2

    assert client.get("/api/matches/status").json()["ai_enabled"] is False  # no key in tests


def test_no_consent_means_no_ai_calls(
    client: TestClient, queue: InlineQueue, fake_ai: FakeAIProvider
) -> None:
    headers = setup_user(client, queue)
    client.post("/api/matches/rescore", headers=headers)
    assert fake_ai.calls == [] and fake_ai.embed_calls == []
    assert {j["match"]["method"] for j in jobs(client)} == {"lexical"}


def test_priority_changes_rank(client: TestClient, queue: InlineQueue) -> None:
    headers = setup_user(client, queue)
    client.post("/api/matches/rescore", headers=headers)
    items = jobs(client)
    last = items[-1]
    resp = client.patch(f"/api/jobs/{last['id']}", json={"priority": 2}, headers=headers)
    assert resp.status_code == 200 and resp.json()["priority"] == 2
    bumped = next(j for j in jobs(client) if j["id"] == last["id"])
    assert bumped["match"]["rank_score"] > last["match"]["rank_score"]
    assert (
        client.patch(f"/api/jobs/{last['id']}", json={"priority": 5}, headers=headers).status_code
        == 422
    )
