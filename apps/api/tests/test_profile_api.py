import copy
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import register, upload
from tests.helpers import fixture_text

SNEHA = fixture_text("sneha_backend.txt")


def _put(client: TestClient, headers: dict[str, str], data: Any, prefs: Any) -> Any:
    return client.put("/api/profile", json={"data": data, "preferences": prefs}, headers=headers)


def test_preferences_before_any_resume(client: TestClient) -> None:
    headers = register(client)
    assert client.get("/api/profile").json() is None
    prefs = {
        "target_roles": ["Backend Engineer", "backend engineer", "  Python  Developer "],
        "remote_scope": "india",
        "onsite_locations": ["Bangalore", "bengaluru", "Remote", "Hyderabad"],
        "open_to": ["full_time", "contract", "full_time"],
        "min_salary": 1200000,
        "currency": "inr",
        "salary_unknown_policy": "include",
    }
    resp = _put(client, headers, {}, prefs)
    assert resp.status_code == 200, resp.text
    saved = resp.json()["preferences"]
    assert saved["target_roles"] == ["Backend Engineer", "Python Developer"]
    assert saved["onsite_locations"] == ["Bengaluru", "Hyderabad"]
    assert saved["open_to"] == ["full_time", "contract"]
    assert saved["currency"] == "INR"
    assert resp.json()["origin"] == "edited"


def test_preferences_validation(client: TestClient) -> None:
    headers = register(client)
    bad = [
        {"remote_scope": "anywhere"},
        {"open_to": []},
        {"open_to": ["freelance"]},
        {"min_salary": 100},  # no currency
        {"min_salary": -5, "currency": "INR"},
        {"currency": "RUPEES"},
    ]
    for prefs in bad:
        assert _put(client, headers, {}, prefs).status_code == 422, prefs


def test_parse_keeps_preferences_and_edits_create_versions(client: TestClient) -> None:
    headers = register(client)
    _put(client, headers, {}, {"remote_scope": "worldwide", "target_roles": ["Backend Engineer"]})
    upload(client, headers, "sneha.txt", SNEHA.encode())

    profile = client.get("/api/profile").json()
    assert profile["version"] == 2
    assert profile["preferences"]["remote_scope"] == "worldwide"  # carried into the parsed version

    data = copy.deepcopy(profile["data"])
    data["skills"] = [s for s in data["skills"] if s["name"] != "SQL"]
    data["skills"].append({"name": "Kubernetes", "source": "user"})
    resp = _put(client, headers, data, profile["preferences"])
    assert resp.status_code == 200, resp.text
    edited = resp.json()
    assert edited["version"] == 3 and edited["origin"] == "edited"
    skills = {s["name"]: s for s in edited["data"]["skills"]}
    assert "SQL" not in skills
    assert skills["Kubernetes"]["source"] == "user"
    assert skills["Kubernetes"]["source_span"] is None
    assert skills["Python"]["source_span"] is not None
    assert edited["experience_months"] == 22


def test_edit_cannot_pass_off_invented_claims_as_resume_facts(client: TestClient) -> None:
    headers = register(client)
    upload(client, headers, "sneha.txt", SNEHA.encode())
    profile = client.get("/api/profile").json()

    forged_skill = copy.deepcopy(profile["data"])
    forged_skill["skills"].append(
        {"name": "Kubernetes", "source": "resume", "evidence": "Expert in Kubernetes"}
    )
    resp = _put(client, headers, forged_skill, profile["preferences"])
    assert resp.status_code == 422
    assert "Kubernetes" in resp.json()["detail"]

    renamed = copy.deepcopy(profile["data"])
    renamed["experience"][0]["title"] = "Engineering Manager"
    assert _put(client, headers, renamed, profile["preferences"]).status_code == 422

    forged_bullet = copy.deepcopy(profile["data"])
    forged_bullet["experience"][0]["bullets"].append(
        {"text": "Led a team of 10 engineers", "source": "resume"}
    )
    assert _put(client, headers, forged_bullet, profile["preferences"]).status_code == 422

    # Client-supplied spans are ignored and recomputed.
    spoofed = copy.deepcopy(profile["data"])
    spoofed["skills"][0]["source_span"] = {"start": 0, "end": 1}
    resp = _put(client, headers, spoofed, profile["preferences"])
    assert resp.status_code == 200
    assert (
        resp.json()["data"]["skills"][0]["source_span"]
        == profile["data"]["skills"][0]["source_span"]
    )
    assert client.get("/api/profile/versions").json()[0]["version"] == 2
