import httpx

from app.core.config import Settings


def make_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """HTTP client for job sources: identifies itself, times out, never sends cookies."""
    return httpx.Client(
        headers={"User-Agent": settings.connector_user_agent, "Accept": "application/json"},
        timeout=httpx.Timeout(settings.connector_timeout_seconds),
        follow_redirects=False,
        transport=transport,
    )
