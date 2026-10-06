from unittest.mock import patch

from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError


def test_health_reports_db_and_redis_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_health_degraded_when_redis_down(client: TestClient) -> None:
    with patch("fakeredis.FakeRedis.ping", side_effect=RedisConnectionError("down")):
        resp = client.get("/api/health")
    assert resp.status_code == 503
    assert resp.json()["redis"] == "error"
    assert resp.json()["database"] == "ok"
