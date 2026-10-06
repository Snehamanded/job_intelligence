from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeAIProvider
from tests.conftest import InlineQueue, give_consent, register, upload
from tests.helpers import ai_fixture, fixture_text, make_docx, make_pdf

SNEHA = fixture_text("sneha_backend.txt")
ARJUN = fixture_text("arjun_data.txt")


def test_upload_txt_without_consent_uses_heuristic_parser(
    client: TestClient, fake_ai: FakeAIProvider
) -> None:
    headers = register(client)
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())

    stored = client.get(f"/api/resumes/{resume['id']}").json()
    assert stored["status"] == "parsed"
    assert "AI parsing is off" in stored["parse_notice"]
    assert fake_ai.calls == []

    profile = client.get("/api/profile").json()
    assert profile["version"] == 1
    assert profile["parse_method"] == "heuristic"
    assert profile["resume_id"] == resume["id"]
    assert profile["experience_months"] == 22
    assert profile["data"]["contact"]["email"] == "sneha.rao@example.com"


def test_upload_with_consent_uses_llm_and_excludes_unsupported(
    client: TestClient, fake_ai: FakeAIProvider
) -> None:
    headers = register(client)
    give_consent(client, headers)
    fake_ai.responses.append(ai_fixture("sneha_backend.invented_claims.json"))
    upload(client, headers, "sneha.txt", SNEHA.encode())

    profile = client.get("/api/profile").json()
    assert profile["parse_method"] == "llm"
    skills = {s["name"] for s in profile["data"]["skills"]}
    assert "Kubernetes" not in skills and "pytest" in skills
    unsupported = {u["label"] for u in profile["data"]["unsupported"]}
    assert "Kubernetes" in unsupported
    # The resume text is sent as delimited data.
    assert "<resume_text>" in fake_ai.calls[0].prompt
    assert "Acme Analytics" in fake_ai.calls[0].prompt


def test_llm_failure_falls_back_to_heuristic(client: TestClient, fake_ai: FakeAIProvider) -> None:
    headers = register(client)
    give_consent(client, headers)
    fake_ai.responses.extend(["{broken", "{broken"])
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())

    stored = client.get(f"/api/resumes/{resume['id']}").json()
    assert stored["status"] == "parsed"
    assert "AI parsing failed" in stored["parse_notice"]
    assert client.get("/api/profile").json()["parse_method"] == "heuristic"


def test_pdf_and_docx_uploads(client: TestClient) -> None:
    headers = register(client)
    pdf = upload(client, headers, "Sneha CV.pdf", make_pdf(SNEHA.replace("•", "-").splitlines()))
    docx = upload(client, headers, "arjun.docx", make_docx(ARJUN.splitlines()))

    resumes = client.get("/api/resumes").json()
    assert {r["id"] for r in resumes} == {pdf["id"], docx["id"]}
    assert all(r["status"] == "parsed" for r in resumes)
    assert next(r for r in resumes if r["id"] == pdf["id"])["page_count"] == 1

    profile = client.get("/api/profile").json()
    assert profile["version"] == 2
    assert profile["data"]["contact"]["name"] == "Arjun Mehta"

    file = client.get(f"/api/resumes/{docx['id']}/file")
    assert file.status_code == 200
    assert file.headers["content-disposition"] == 'attachment; filename="resume.docx"'
    assert file.headers["x-content-type-options"] == "nosniff"


def test_rejected_uploads(client: TestClient) -> None:
    headers = register(client)
    cases = [
        ("cv.pdf", b"plain text pretending", 415),
        ("cv.exe", b"MZ\x90\x00binary", 415),
        ("cv.txt", b"", 415),
    ]
    for name, data, code in cases:
        resp = client.post("/api/resumes", files={"file": (name, data)}, headers=headers)
        assert resp.status_code == code, (name, resp.text)
    assert client.get("/api/resumes").json() == []


def test_oversize_upload(client: TestClient, monkeypatch: object) -> None:
    from app.core.config import get_settings

    headers = register(client)
    settings = get_settings()
    original = settings.max_upload_bytes
    settings.max_upload_bytes = 100
    try:
        resp = client.post("/api/resumes", files={"file": ("cv.txt", b"x" * 101)}, headers=headers)
    finally:
        settings.max_upload_bytes = original
    assert resp.status_code == 413


def test_scanned_pdf_fails_with_clear_message(client: TestClient) -> None:
    headers = register(client)
    resume = upload(client, headers, "scan.pdf", make_pdf([]))
    stored = client.get(f"/api/resumes/{resume['id']}").json()
    assert stored["status"] == "failed"
    assert "scanned image" in stored["error_message"]
    assert client.get("/api/profile").json() is None


def test_reparse_after_consent_creates_new_version(
    client: TestClient, fake_ai: FakeAIProvider
) -> None:
    headers = register(client)
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())
    give_consent(client, headers)
    fake_ai.responses.append(ai_fixture("sneha_backend.invented_claims.json"))

    resp = client.post(f"/api/resumes/{resume['id']}/reparse", headers=headers)
    assert resp.status_code == 202
    profile = client.get("/api/profile").json()
    assert (profile["version"], profile["parse_method"]) == (2, "llm")
    versions = client.get("/api/profile/versions").json()
    assert [(v["version"], v["is_current"]) for v in versions] == [(2, True), (1, False)]


def test_reparse_while_queued_conflicts(client: TestClient, queue: InlineQueue) -> None:
    headers = register(client)
    queue.paused = True
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())
    assert client.get(f"/api/resumes/{resume['id']}").json()["status"] == "queued"
    resp = client.post(f"/api/resumes/{resume['id']}/reparse", headers=headers)
    assert resp.status_code == 409


def test_delete_resume_removes_file_and_keeps_profile(client: TestClient, storage: object) -> None:
    headers = register(client)
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())
    assert client.delete(f"/api/resumes/{resume['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/resumes/{resume['id']}").status_code == 404
    profile = client.get("/api/profile").json()
    assert profile["resume_id"] is None
    assert profile["data"]["contact"]["name"] == "Sneha Rao"


def test_users_cannot_see_each_others_resumes(client: TestClient) -> None:
    headers = register(client, email="a@example.com")
    resume = upload(client, headers, "sneha.txt", SNEHA.encode())
    client.post("/api/auth/logout", headers=headers)

    other = register(client, email="b@example.com")
    for method, path in [
        ("GET", f"/api/resumes/{resume['id']}"),
        ("GET", f"/api/resumes/{resume['id']}/file"),
        ("POST", f"/api/resumes/{resume['id']}/reparse"),
        ("DELETE", f"/api/resumes/{resume['id']}"),
    ]:
        assert client.request(method, path, headers=other).status_code == 404, path
    assert client.get("/api/resumes").json() == []
    assert client.get("/api/profile").json() is None


def test_upload_requires_auth_and_csrf(client: TestClient) -> None:
    headers = register(client)
    resp = client.post("/api/resumes", files={"file": ("cv.txt", SNEHA.encode())})
    assert resp.status_code == 403
    client.post("/api/auth/logout", headers=headers)
    resp = client.post("/api/resumes", files={"file": ("cv.txt", SNEHA.encode())}, headers=headers)
    assert resp.status_code in (401, 403)


def test_uploads_are_rate_limited_per_user(client: TestClient) -> None:
    from app.core.config import get_settings

    headers = register(client)
    settings = get_settings()
    original = settings.ai_rate_limit
    settings.ai_rate_limit = 2
    try:
        codes = [
            client.post(
                "/api/resumes", files={"file": ("cv.txt", SNEHA.encode())}, headers=headers
            ).status_code
            for _ in range(3)
        ]
    finally:
        settings.ai_rate_limit = original
    assert codes == [202, 202, 429]
