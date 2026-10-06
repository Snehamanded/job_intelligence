"""RSS parsing for job feeds. Feeds are untrusted XML, so defusedxml blocks entity attacks."""

from datetime import datetime
from email.utils import parsedate_to_datetime

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.connectors.base import ConnectorError


def items(xml: str, label: str) -> list[dict[str, str]]:
    """Each <item> as {tag: text}, with namespaces dropped ("content:encoded" -> "encoded")."""
    try:
        root = ElementTree.fromstring(xml)
    except (DefusedXmlException, ElementTree.ParseError) as exc:
        raise ConnectorError(f"{label} returned a feed that couldn't be read safely") from exc
    result = []
    for item in root.iter("item"):
        fields: dict[str, str] = {}
        for child in item:
            tag = child.tag.rsplit("}", 1)[-1]
            fields.setdefault(tag, (child.text or "").strip())
        result.append(fields)
    return result


def rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
