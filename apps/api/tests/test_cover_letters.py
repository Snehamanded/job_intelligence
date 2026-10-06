import io
import json
from typing import Any

import docx
from fastapi.testclient import TestClient

from app.ai.providers.base import AIProviderError
from app.ai.providers.fake import FakeAIProvider
from app.services.cover_letters.checks import check_claim, check_company, check_connective
from tests.conftest import InlineQueue, give_consent, register, upload
from tests.helpers import fixture_text

JOB = {
    "title": "Backend Engineer",
    "company": "Acme Payments",
    "location": "Bengaluru, India",
    "description": "We need PostgreSQL, Python and FastAPI to build REST APIs for our payments platform. 1-3 years of experience. Full-time.",
}
POSTING = f"{JOB['title']}\n{JOB['description']}"
TEXTS = {
    "r0b0": "Built REST APIs in FastAPI serving 2,000 daily users",
    "r0b1": "Reduced report generation time by 40% by adding PostgreSQL indexes",
}

# --- code checks ------------------------------------------------------------------------------


def test_claim_checks() -> None:
    assert check_claim("I built REST APIs in FastAPI for 2,000 daily users.", ["r0b0"], TEXTS) == []
    assert check_claim("I am a strong engineer.", [], TEXTS)[0].startswith("A statement about you")
    assert any("75" in i for i in check_claim("I cut report time by 75%.", ["r0b1"], TEXTS))
    assert any(
        "Kubernetes" in i for i in check_claim("I built APIs on Kubernetes.", ["r0b0"], TEXTS)
    )


def test_company_checks() -> None:
    quote = "build REST APIs for our payments platform"
    assert check_company("You build REST APIs for a payments platform.", quote, POSTING) == []
    assert check_company("You build payments.", None, POSTING)[0].startswith(
        "A statement about the company"
    )
    assert check_company("Founded in 1999.", "founded in 1999", POSTING) == [
        "The quoted text isn't in the job posting"
    ]
    assert any(
        "Kafka" in i for i in check_company("You build REST APIs with Kafka.", quote, POSTING)
    )


def test_connective_checks() -> None:
    assert check_connective("I would welcome the chance to talk.") == []
    assert check_connective("I have managed a team of 10 engineers.") == [
        "States a number without a source"
    ]
    assert check_connective("I love Python.") == ["Mentions Python without citing your resume"]


# --- end to end -------------------------------------------------------------------------------

DRAFT = {
    "paragraphs": [
        {"sentences": [
            {"text": "I'm writing to apply for the Backend Engineer role at Acme Payments.", "kind": "connective"},
            {"text": "Your team builds REST APIs with Python, FastAPI and PostgreSQL.", "kind": "company",
             "job_quote": "We need PostgreSQL, Python and FastAPI to build REST APIs"},
            {"text": "Acme Payments was founded in 1999.", "kind": "company", "job_quote": "founded in 1999"},
        ]},
        {"sentences": [
            {"text": "At Acme Analytics I built REST APIs in FastAPI serving 2,000 daily users.", "kind": "claim", "sources": ["r0b0", "r0"]},
            {"text": "I reduced report generation time by 75% with PostgreSQL indexes.", "kind": "claim", "sources": ["r0b1"]},
            {"text": "I deployed those services on Kubernetes.", "kind": "claim", "sources": ["r0b0"]},
            {"text": "I also mentored junior engineers on testing.", "kind": "claim", "sources": ["r0b2"]},
            {"text": "I am a Python expert.", "kind": "claim", "sources": []},
            {"text": "I have managed a team of 10 engineers.", "kind": "connective"},
        ]},
        {"sentences": [{"text": "I would welcome the chance to discuss the role.", "kind": "connective"}]},
    ]
}  # fmt: skip
VERIFY = {
    "results": [
        {"sentence_id": "a0-0", "supported": True},
        {"sentence_id": "a0-1", "supported": True},
        {"sentence_id": "a1-0", "supported": True},
        {
            "sentence_id": "a1-3",
            "supported": False,
            "problems": ["Mentoring isn't stated in the cited text"],
        },
        {"sentence_id": "a2-0", "supported": True},
    ]
}


def setup(client: TestClient, queue: InlineQueue, *, consent: bool) -> tuple[dict[str, str], str]:
    headers = register(client)
    upload(client, headers, "sneha.txt", fixture_text("sneha_backend.txt").encode())
    job_id: str = client.post("/api/jobs/import", json=JOB, headers=headers).json()["id"]
    if consent:
        queue.paused = True
        give_consent(client, headers)
        queue.paused = False
    return headers, job_id


def start(client: TestClient, headers: dict[str, str], job_id: str, **body: Any) -> dict[str, Any]:
    resp = client.post("/api/cover-letters", json={"job_id": job_id, **body}, headers=headers)
    assert resp.status_code == 202, resp.text
    detail: dict[str, Any] = client.get(f"/api/cover-letters/{resp.json()['id']}").json()
    return detail


def sentences(letter: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["id"]: s for p in letter["paragraphs"] for s in p["sentences"]}


def test_ai_letter_end_to_end(
    client: TestClient, queue: InlineQueue, fake_ai: FakeAIProvider
) -> None:
    headers, job_id = setup(client, queue, consent=True)
    fake_ai.responses.extend([json.dumps(DRAFT), json.dumps(VERIFY)])
    letter = start(client, headers, job_id, tone="warm", length="short")
    assert (letter["status"], letter["method"], letter["tone"]) == ("ready", "ai", "warm")

    s = sentences(letter)
    assert s["a0-1"]["status"] == "proposed" and s["a0-1"]["included"]
    assert s["a0-2"]["issues"] == ["The quoted text isn't in the job posting"]
    assert "75" in s["a1-1"]["issues"][0]
    assert "Kubernetes" in s["a1-2"]["issues"][0]
    assert s["a1-3"]["issues"] == ["Second check: Mentoring isn't stated in the cited text"]
    assert s["a1-4"]["issues"][0].startswith("A statement about you")
    assert s["a1-5"]["issues"] == ["States a number without a source"]
    unsupported = [k for k, v in s.items() if v["status"] == "unsupported"]
    assert sorted(unsupported) == ["a0-2", "a1-1", "a1-2", "a1-3", "a1-4", "a1-5"]
    assert all(not s[k]["included"] for k in unsupported)
    assert "1999" not in " ".join(letter["preview"]) and "75%" not in " ".join(letter["preview"])

    verify_call = fake_ai.calls[-1]
    assert (
        "a1-0" in verify_call.prompt and "a1-1" not in verify_call.prompt
    )  # only code-passed ones
    assert "<job_posting>" in fake_ai.calls[-2].prompt

    url = f"/api/cover-letters/{letter['id']}/sentences"
    refused = client.patch(url, json={"updates": {"a1-1": {"included": True}}}, headers=headers)
    assert refused.status_code == 422 and "can't be included" in refused.json()["detail"]

    edited = client.patch(
        url,
        json={
            "updates": {
                "a1-1": {
                    "text": "I reduced report generation time by 40% with PostgreSQL indexes."
                },
                "a2-0": {"included": False},
            },
            "add": [
                {"paragraph_id": "p2", "text": "I'm based in Bengaluru and can start in November."}
            ],
        },
        headers=headers,
    ).json()
    s = sentences(edited)
    assert (s["a1-1"]["source"], s["a1-1"]["status"], s["a1-1"]["included"]) == (
        "user",
        "proposed",
        True,
    )
    assert s["a2-0"]["included"] is False
    added = [x for x in s.values() if x["text"].startswith("I'm based in Bengaluru")]
    assert added and added[0]["source"] == "user"

    saved = client.post(
        f"/api/cover-letters/{letter['id']}/save", json={"name": "Acme letter"}, headers=headers
    ).json()
    assert saved["status"] == "saved" and saved["signature"] == "Sneha Rao"
    text = " ".join(saved["preview"])
    assert "by 40%" in text and "Bengaluru" in text and "I would welcome" not in text
    for banned in ("1999", "75%", "Kubernetes", "mentored", "Python expert", "team of 10"):
        assert banned not in text

    assert (
        client.patch(
            url, json={"updates": {"a0-0": {"included": False}}}, headers=headers
        ).status_code
        == 409
    )
    resp = client.get(f"/api/cover-letters/{letter['id']}/docx")
    assert (
        resp.status_code == 200
        and 'filename="Acme-letter.docx"' in resp.headers["content-disposition"]
    )
    doc_text = "\n".join(p.text for p in docx.Document(io.BytesIO(resp.content)).paragraphs)
    assert doc_text.startswith("Dear Hiring Team at Acme Payments,") and "Sneha Rao" in doc_text
    assert "1999" not in doc_text

    exported = client.get("/api/me/export").json()["cover_letters"]
    assert exported[0]["name"] == "Acme letter" and exported[0]["content"]["paragraphs"]


def test_verifier_unavailable(
    client: TestClient, queue: InlineQueue, fake_ai: FakeAIProvider
) -> None:
    headers, job_id = setup(client, queue, consent=True)
    fake_ai.responses.extend([json.dumps(DRAFT), AIProviderError("down", retryable=False)])
    letter = start(client, headers, job_id)
    s = sentences(letter)
    assert all(v["status"] == "unsupported" for v in s.values())
    assert "Couldn't be checked" in s["a1-0"]["issues"][0]
    assert letter["preview"] == []


def test_template_letter_without_consent(
    client: TestClient, queue: InlineQueue, fake_ai: FakeAIProvider
) -> None:
    headers, job_id = setup(client, queue, consent=False)
    letter = start(client, headers, job_id)
    assert (letter["status"], letter["method"]) == ("ready", "template")
    assert "template letter" in letter["notice"]
    assert fake_ai.calls == []
    s = list(sentences(letter).values())
    assert all(x["status"] == "proposed" and x["source"] == "template" for x in s)
    text = " ".join(letter["preview"])
    assert (
        "As Software Engineer at Acme Analytics Pvt Ltd, I built REST APIs in FastAPI serving 2,000 daily users."
        in text
    )
    assert "My skills include PostgreSQL, Python and FastAPI" in text
    saved = client.post(f"/api/cover-letters/{letter['id']}/save", json={}, headers=headers)
    assert saved.status_code == 200


def test_validation_and_isolation(client: TestClient, queue: InlineQueue) -> None:
    headers, job_id = setup(client, queue, consent=False)
    bad_base = client.post(
        "/api/cover-letters",
        json={"job_id": job_id, "resume_version_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert bad_base.status_code == 422
    assert (
        client.post(
            "/api/cover-letters", json={"job_id": job_id, "tone": "angry"}, headers=headers
        ).status_code
        == 422
    )
    letter = start(client, headers, job_id)
    client.post("/api/auth/logout", headers=headers)
    other = register(client, email="other@example.com")
    assert client.get(f"/api/cover-letters/{letter['id']}").status_code == 404
    assert client.get(f"/api/cover-letters/{letter['id']}/docx").status_code == 404
    assert (
        client.patch(
            f"/api/cover-letters/{letter['id']}/sentences", json={}, headers=other
        ).status_code
        == 404
    )
    assert client.get("/api/cover-letters").json() == []


def test_letter_from_saved_tailored_version(client: TestClient, queue: InlineQueue) -> None:
    headers, job_id = setup(client, queue, consent=False)
    version = client.post("/api/tailoring", json={"job_id": job_id}, headers=headers).json()
    client.post(f"/api/tailoring/{version['id']}/save", json={}, headers=headers)
    letter = start(client, headers, job_id, resume_version_id=version["id"])
    assert letter["resume_version_id"] == version["id"] and letter["status"] == "ready"
