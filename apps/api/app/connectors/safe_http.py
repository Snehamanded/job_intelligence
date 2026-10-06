"""Fetching user-supplied URLs without SSRF: public addresses only, robots.txt respected.

Only used for one-off imports of a job page the user pasted. Never crawls.
"""

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

MAX_REDIRECTS = 3
Resolver = Callable[[str], list[str]]


class UnsafeURLError(Exception):
    """The URL can't be fetched safely or politely. Message is safe to show the user."""


def system_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError("That website's address couldn't be found.") from exc
    return [str(info[4][0]) for info in infos]


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback)


def check_url(url: str, resolve: Resolver) -> str:
    """Return the URL if it is http(s), on a default port, and resolves only to public IPs."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http:// and https:// links can be imported.")
    if parts.username or parts.password:
        raise UnsafeURLError("Links with embedded credentials can't be imported.")
    if not parts.hostname:
        raise UnsafeURLError("That link has no website address.")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("That link's port is invalid.") from exc
    if port not in (None, 80, 443):
        raise UnsafeURLError("Only links on standard web ports can be imported.")
    addresses = resolve(parts.hostname)
    if not addresses or not all(_public(a) for a in addresses):
        raise UnsafeURLError(
            "That address points to a private or local network, so it can't be fetched."
        )
    return url.strip()


class SafeFetcher:
    def __init__(
        self,
        client: httpx.Client,
        *,
        user_agent: str,
        max_bytes: int,
        resolve: Resolver = system_resolver,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._max_bytes = max_bytes
        self._resolve = resolve

    def _get(
        self,
        url: str,
        *,
        html_only: bool,
        check_redirect: Callable[[str], None] | None = None,
    ) -> tuple[str, str] | None:
        """(final_url, text), or None on 404. Follows redirects only after re-checking them."""
        for _ in range(MAX_REDIRECTS + 1):
            url = check_url(url, self._resolve)
            try:
                with self._client.stream("GET", url, follow_redirects=False) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise UnsafeURLError("The page redirected without a destination.")
                        url = urljoin(url, location)
                        if check_redirect is not None:
                            check_redirect(url)
                        continue
                    if response.status_code == 404:
                        return None
                    if response.status_code >= 400:
                        raise UnsafeURLError(f"The page returned HTTP {response.status_code}.")
                    ctype = response.headers.get("content-type", "")
                    if html_only and "html" not in ctype:
                        raise UnsafeURLError("That link isn't a web page.")
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > self._max_bytes:
                            raise UnsafeURLError("That page is too large to import.")
                    return url, body.decode(response.encoding or "utf-8", errors="replace")
            except httpx.TimeoutException as exc:
                raise UnsafeURLError("The page took too long to respond.") from exc
            except httpx.HTTPError as exc:
                raise UnsafeURLError("The page couldn't be reached.") from exc
        raise UnsafeURLError("The page redirected too many times.")

    def allowed_by_robots(self, url: str) -> bool:
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            found = self._get(robots_url, html_only=False)
        except UnsafeURLError:
            return True  # an unreadable robots.txt doesn't forbid; the page itself is still checked
        if found is None:
            return True
        parser = RobotFileParser()
        parser.parse(found[1].splitlines())
        return parser.can_fetch(self._user_agent, url)

    def fetch_page(
        self, url: str, refuse: Callable[[str], str | None] | None = None
    ) -> tuple[str, str]:
        """`refuse(url)` names a site that must never be fetched; checked on every redirect too,
        so a short link can't lead to one."""

        def check(target: str) -> None:
            if refuse is not None and (site := refuse(target)):
                raise UnsafeURLError(
                    f"The link leads to {site}, which doesn't allow automated access."
                )
            if not self.allowed_by_robots(target):
                raise UnsafeURLError(
                    "This website's robots.txt doesn't allow automated access to that page."
                )

        check_url(url, self._resolve)
        check(url)
        found = self._get(url, html_only=True, check_redirect=check)
        if found is None:
            raise UnsafeURLError("That page wasn't found.")
        return found
