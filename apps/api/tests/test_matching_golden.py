"""Golden set: fixed fictional resumes x jobs with an expected rank order (code-only scoring).

If a scoring change reorders these, the change needs a deliberate update here.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import InlineQueue, register, upload
from tests.helpers import fixture_text

JOBS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "golden" / "jobs.json").read_text()
)

# Expected order as tiers: jobs within a tier are equally (un)suitable, so their order is free.
CASES = {
    "sneha_backend.txt": (
        {"target_roles": ["Backend Engineer", "Python Developer"], "remote_scope": "india",
         "onsite_locations": ["Bengaluru"]},
        [{"backend_python"}, {"fullstack_js"}, {"senior_go"}, {"data_analyst"}, {"sales_manager"}],
    ),
    "arjun_data.txt": (
        {"target_roles": ["Data Analyst"], "remote_scope": "india", "onsite_locations": ["Pune"]},
        [{"data_analyst"}, {"backend_python"}, {"fullstack_js", "senior_go", "sales_manager"}],
    ),
}  # fmt: skip


@pytest.mark.parametrize("resume", sorted(CASES))
def test_golden_rank_order(client: TestClient, queue: InlineQueue, resume: str) -> None:
    prefs, expected = CASES[resume]
    headers = register(client)
    upload(client, headers, resume, fixture_text(resume).encode())
    profile = client.get("/api/profile").json()
    client.put(
        "/api/profile", json={"data": profile["data"], "preferences": prefs}, headers=headers
    )
    queue.paused = True  # import everything, then score once
    titles = {}
    for job in JOBS:
        body = {k: job[k] for k in ("title", "company", "location", "description")}
        resp = client.post("/api/jobs/import", json=body, headers=headers)
        assert resp.status_code == 201, resp.text
        titles[resp.json()["id"]] = job["key"]
    queue.paused = False
    client.post("/api/matches/rescore", headers=headers)

    items = client.get("/api/jobs", params={"eligible_only": False, "sort": "rank"}).json()["items"]
    order = [titles[j["id"]] for j in items]
    scores = {titles[j["id"]]: j["match"]["match_score"] for j in items}
    tiers = []
    for tier in expected:
        tiers.append(set(order[: len(tier)]))
        order = order[len(tier) :]
    assert tiers == expected, scores
    assert all(j["match"]["method"] == "lexical" for j in items)
