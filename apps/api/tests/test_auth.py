from fastapi.testclient import TestClient

from tests.conftest import csrf, register


def test_register_sets_session_and_me_returns_user(client: TestClient) -> None:
    register(client, email="  Sneha@Example.com ")
    assert "access_token" in client.cookies
    resp = client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "sneha@example.com"
    assert "password_hash" not in resp.json()


def test_session_cookie_is_httponly_and_lax(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "correct-horse-1"},
        headers=csrf(client),
    )
    cookies = [v.lower() for k, v in resp.headers.multi_items() if k == "set-cookie"]
    access = next(c for c in cookies if c.startswith("access_token="))
    assert "httponly" in access
    assert "samesite=lax" in access


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    register(client)
    resp = client.post(
        "/api/auth/register",
        json={"email": "SNEHA@example.com", "password": "another-pass-1"},
        headers=csrf(client),
    )
    assert resp.status_code == 409


def test_register_rejects_short_password(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "short"},
        headers=csrf(client),
    )
    assert resp.status_code == 422


def test_login_logout_flow(client: TestClient) -> None:
    headers = register(client)
    client.post("/api/auth/logout", headers=headers)
    assert client.get("/api/me").status_code == 401

    resp = client.post(
        "/api/auth/login",
        json={"email": "sneha@example.com", "password": "correct-horse-1"},
        headers=csrf(client),
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "sneha@example.com"
    assert client.get("/api/me").status_code == 200


def test_login_wrong_password(client: TestClient) -> None:
    headers = register(client)
    client.post("/api/auth/logout", headers=headers)
    resp = client.post(
        "/api/auth/login",
        json={"email": "sneha@example.com", "password": "wrong-password"},
        headers=csrf(client),
    )
    assert resp.status_code == 401
    assert client.get("/api/me").status_code == 401


def test_login_unknown_email_same_error(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-123"},
        headers=csrf(client),
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


def test_protected_route_requires_auth(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/settings").status_code == 401


def test_tampered_token_rejected(client: TestClient) -> None:
    register(client)
    token = client.cookies["access_token"]
    client.cookies.set("access_token", token[:-2] + ("aa" if token[-2:] != "aa" else "bb"))
    assert client.get("/api/me").status_code == 401


def test_mutating_request_without_csrf_rejected(client: TestClient) -> None:
    client.get("/api/auth/csrf")  # cookie present, header missing
    resp = client.post(
        "/api/auth/register", json={"email": "a@example.com", "password": "correct-horse-1"}
    )
    assert resp.status_code == 403


def test_mutating_request_with_wrong_csrf_rejected(client: TestClient) -> None:
    headers = register(client)
    resp = client.put(
        "/api/settings", json={"llm_consent": True}, headers={"X-CSRF-Token": "forged"}
    )
    assert resp.status_code == 403
    assert (
        client.put("/api/settings", json={"llm_consent": True}, headers=headers).status_code == 200
    )


def test_login_rotates_csrf_token(client: TestClient) -> None:
    before = csrf(client)
    resp = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "correct-horse-1"},
        headers=before,
    )
    after = resp.json()["csrf_token"]
    assert after != before["X-CSRF-Token"]
    # The pre-login token no longer works.
    assert (
        client.put("/api/settings", json={"llm_consent": True}, headers=before).status_code == 403
    )


def test_auth_endpoints_rate_limited(client: TestClient) -> None:
    headers = csrf(client)
    body = {"email": "nobody@example.com", "password": "whatever-123"}
    statuses = [
        client.post("/api/auth/login", json=body, headers=headers).status_code for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_settings_consent_roundtrip(client: TestClient) -> None:
    headers = register(client)
    assert client.get("/api/settings").json() == {"llm_consent": False, "llm_consent_at": None}
    resp = client.put("/api/settings", json={"llm_consent": True}, headers=headers)
    assert resp.json()["llm_consent"] is True
    assert resp.json()["llm_consent_at"] is not None
    resp = client.put("/api/settings", json={"llm_consent": False}, headers=headers)
    assert resp.json() == {"llm_consent": False, "llm_consent_at": None}
