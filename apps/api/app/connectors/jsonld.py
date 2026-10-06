"""Read schema.org JobPosting JSON-LD from a career page (the format search engines index)."""

import hashlib
import json
import re
from typing import Any

from app.connectors.common import employment, parse_time, structured_salary
from app.services.jobs.normalize import RawPosting
from app.utils.html_text import html_to_text
from app.utils.salary import Period, Salary

_SCRIPT = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S
)
_UNITS: dict[str, Period] = {"YEAR": "year", "MONTH": "month", "HOUR": "hour"}
_EMPLOYMENT = {"FULL_TIME": "full_time", "PART_TIME": "part_time", "CONTRACTOR": "contract",
               "TEMPORARY": "contract", "INTERN": "internship"}  # fmt: skip


def _nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [n for item in value for n in _nodes(item)]
    if isinstance(value, dict):
        return [value, *_nodes(value.get("@graph", []))]
    return []


def _is_job(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    return kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind)


def find_job_postings(html: str) -> list[dict[str, Any]]:
    jobs = []
    for block in _SCRIPT.findall(html):
        text = block.strip().removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(text)
        except ValueError:
            continue
        jobs += [n for n in _nodes(data) if _is_job(n)]
    return jobs


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value or "")


def _locations(job: dict[str, Any]) -> str:
    places = []
    raw = job.get("jobLocation")
    for loc in raw if isinstance(raw, list) else [raw] if raw else []:
        address = (loc or {}).get("address") or {}
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"),
                     _name(address.get("addressCountry"))]  # fmt: skip
            places.append(", ".join(str(p) for p in parts if p))
    if job.get("jobLocationType") == "TELECOMMUTE":
        reqs = job.get("applicantLocationRequirements")
        regions = [_name(r) for r in (reqs if isinstance(reqs, list) else [reqs] if reqs else [])]
        remote = [f"Remote, {r}" for r in regions if r] or ["Remote"]
        places = remote + places
    return "; ".join(p for p in places if p)


def _salary(job: dict[str, Any]) -> Salary | None:
    base = job.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value") or {}
    if not isinstance(value, dict):
        value = {"value": value}
    unit = _UNITS.get(str(value.get("unitText", "YEAR")).upper())
    if unit is None:
        return None
    low = value.get("minValue", value.get("value"))
    return structured_salary(low, value.get("maxValue"), base.get("currency"), unit)


def to_posting(job: dict[str, Any], page_url: str) -> RawPosting:
    kinds = job.get("employmentType")
    kind = kinds[0] if isinstance(kinds, list) and kinds else kinds
    identifier = job.get("identifier")
    ident = _name(identifier) or (identifier.get("value") if isinstance(identifier, dict) else "")
    key = hashlib.sha256(f"{page_url}|{ident}|{job.get('title')}".encode()).hexdigest()[:32]
    return RawPosting(
        source="careers",
        source_job_id=key,
        title=html_to_text(str(job.get("title") or "Untitled role")),
        company=_name(job.get("hiringOrganization")) or "Unknown company",
        location_text=_locations(job),
        description_text=html_to_text(str(job.get("description") or "")),
        url=page_url,
        posted_at=parse_time(job.get("datePosted")),
        salary=_salary(job),
        employment_hint=_EMPLOYMENT.get(str(kind).upper()) or employment(kind),  # type: ignore[arg-type]
        raw={k: v for k, v in job.items() if k != "description"},
    )
