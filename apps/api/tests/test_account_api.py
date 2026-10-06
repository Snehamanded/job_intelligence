from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.models import CandidateProfile, Resume, User, UserSettings
from app.services.storage import LocalFileStorage
from tests.conftest import register, upload
from tests.helpers import fixture_text

SNEHA = fixture_text("sneha_backend.txt")


def test_export_contains_all_user_data(client: TestClient) -> None:
    headers = register(client)
    upload(client, headers, "sneha.txt", SNEHA.encode())
    resp = client.get("/api/me/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["user"]["email"] == "sneha@example.com"
    assert "password_hash" not in str(data)
    assert data["resumes"][0]["extracted_text"].startswith("Sneha Rao")
    assert data["profiles"][0]["version"] == 1
    assert data["settings"]["llm_consent"] is False


def test_delete_account_requires_password_and_removes_everything(
    client: TestClient, storage: LocalFileStorage
) -> None:
    headers = register(client)
    upload(client, headers, "sneha.txt", SNEHA.encode())
    user_dir = Path(storage._root) / client.get("/api/me").json()["id"]
    assert any(user_dir.iterdir())

    wrong = client.request("DELETE", "/api/me", json={"password": "nope"}, headers=headers)
    assert wrong.status_code == 403

    resp = client.request(
        "DELETE", "/api/me", json={"password": "correct-horse-1"}, headers=headers
    )
    assert resp.status_code == 204
    assert client.get("/api/me").status_code == 401
    assert not user_dir.exists()
    with get_sessionmaker()() as session:
        for model in (User, UserSettings, Resume, CandidateProfile):
            assert session.scalar(select(func.count()).select_from(model)) == 0
