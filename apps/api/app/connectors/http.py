from typing import Any

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


def get_json(
    client: httpx.Client, url: str, label: str, params: dict[str, str] | None = None
) -> Any:
    """GET JSON from a job source, turning failures into ConnectorError messages for the user."""
    from app.connectors.base import ConnectorError

    try:
        response = client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise ConnectorError(f"{label} timed out") from exc
    except httpx.HTTPError as exc:
        raise ConnectorError(f"Could not reach {label}") from exc
    if response.status_code == 404:
        raise ConnectorError("Not found")
    if response.status_code == 429:
        raise ConnectorError(f"{label} rate limit reached; try again later")
    if response.status_code in (401, 403):
        raise ConnectorError(f"{label} refused access (HTTP {response.status_code})")
    if response.status_code >= 400:
        raise ConnectorError(f"{label} returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ConnectorError(f"{label} returned an unexpected response") from exc
