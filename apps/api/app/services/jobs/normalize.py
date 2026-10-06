"""Turn a connector's raw posting into the normalized job shape. Deterministic, no LLM."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.utils.experience import parse_experience
from app.utils.locations import (
    INDIAN_CITIES,
    canonical_city,
    normalize_country,
    normalize_location,
    normalize_region,
)
from app.utils.salary import Salary, parse_salary

RemoteType = Literal["remote", "hybrid", "onsite", "unknown"]
EmploymentType = Literal["full_time", "contract", "internship", "part_time", "unknown"]


@dataclass
class RawPosting:
    """What a connector returns. Text fields are untrusted."""

    source: str
    source_job_id: str
    title: str
    company: str
    location_text: str
    description_text: str
    url: str | None = None
    posted_at: datetime | None = None
    salary: Salary | None = None  # structured pay from the source, if any
    employment_hint: "EmploymentType | None" = None  # structured type from the source, if any
    is_mock: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LocationInfo:
    display: list[str]
    cities: list[str]
    countries: list[str]
    remote_type: RemoteType
    remote_regions: list[str]


@dataclass
class NormalizedJob:
    source: str
    source_job_id: str
    url: str | None
    title: str
    company: str
    location: LocationInfo
    employment_type: EmploymentType
    salary: Salary | None
    experience_min_years: int | None
    experience_max_years: int | None
    description_text: str
    content_hash: str
    dedupe_key: str
    posted_at: datetime | None
    is_mock: bool
    raw: dict[str, Any]


_SPLIT = re.compile(r"\s*(?:;|\||\bor\b|/(?=\s))\s*", re.IGNORECASE)
_REMOTE = re.compile(r"\bremote\b|work from home|\bwfh\b", re.IGNORECASE)
_HYBRID = re.compile(r"\bhybrid\b", re.IGNORECASE)


def parse_location(location_text: str, title: str = "") -> LocationInfo:
    cities: list[str] = []
    countries: list[str] = []
    regions: list[str] = []
    display: list[str] = []
    remote = bool(_REMOTE.search(title))
    hybrid = bool(_HYBRID.search(title))

    for part in _SPLIT.split(location_text or ""):
        part = part.strip(" ,")
        if not part:
            continue
        if _REMOTE.search(part):
            remote = True
            rest = _REMOTE.sub("", part).strip(" ,-–()")
            part_regions = [
                r
                for piece in re.split(r"\s*[,(]\s*", rest)
                if (r := normalize_region(piece.strip(" )")))
            ]
            regions.extend(r for r in part_regions if r not in regions)
            label = f"Remote ({', '.join(part_regions)})" if part_regions else "Remote"
            if label not in display:
                display.append(label)
            continue
        if _HYBRID.search(part):
            hybrid = True
            part = _HYBRID.sub("", part).strip(" ,-–()")
        pieces = [p.strip() for p in part.split(",") if p.strip()]
        city = canonical_city(pieces[0]) if pieces else None
        country = next((c for p in reversed(pieces) if (c := normalize_country(p))), None)
        if city is None and pieces and normalize_country(pieces[0]) is None:
            city = normalize_location(pieces[0])  # a city we don't know: keep a tidy version
        if city and country is None and city in INDIAN_CITIES:
            country = "India"
        if city and city not in cities and city != country:
            cities.append(city)
        if country and country not in countries:
            countries.append(country)
        label = ", ".join(x for x in (city if city != country else None, country) if x)
        if label and label not in display:
            display.append(label)

    remote_type: RemoteType
    if remote:
        remote_type = "remote"
    elif hybrid:
        remote_type = "hybrid"
    elif cities or countries:
        remote_type = "onsite"
    else:
        remote_type = "unknown"
    return LocationInfo(display, cities, countries, remote_type, regions)


def detect_employment_type(title: str, description: str) -> EmploymentType:
    t = title.lower()
    if re.search(r"\bintern(ship)?\b|\btrainee\b", t):
        return "internship"
    if re.search(r"\bcontract(or)?\b|\bfreelance\b|\bfixed[- ]term\b|\btemporary\b", t):
        return "contract"
    if re.search(r"\bpart[- ]time\b", t):
        return "part_time"
    d = description.lower()
    if re.search(r"\bthis is an? (paid )?internship\b|\binternship (program|duration)\b", d):
        return "internship"
    if re.search(r"\b(this is a|on a) (\d+[- ]month )?contract(ual)? (role|position|basis)\b", d):
        return "contract"
    if re.search(r"\bpart[- ]time (role|position)\b", d):
        return "part_time"
    if re.search(r"\bfull[- ]time\b|\bpermanent\b", d):
        return "full_time"
    return "unknown"


_TITLE_SYNONYMS = [
    (r"\bback[- ]end\b", "backend"),
    (r"\bfront[- ]end\b", "frontend"),
    (r"\bfull[- ]stack\b", "fullstack"),
    (r"\bsr\.?\b", "senior"),
    (r"\bjr\.?\b", "junior"),
    (r"\bswe\b", "software engineer"),
    (r"\bml\b", "machine learning"),
    (r"\bdeveloper\b|\bprogrammer\b", "engineer"),
]
_STOPWORDS = {"a", "an", "the", "of", "and", "for", "in", "at", "to", "with"}


def title_words(text: str) -> list[str]:
    text = text.lower()
    for pattern, replacement in _TITLE_SYNONYMS:
        text = re.sub(pattern, replacement, text)
    return [w for w in re.findall(r"[a-z0-9+#.]+", text) if w not in _STOPWORDS]


def title_matches(title: str, keywords: list[str]) -> bool:
    """True if every word of any keyword appears in the title (with common synonyms)."""
    if not keywords:
        return True
    words = set(title_words(title))
    return any((kw_words := title_words(k)) and all(w in words for w in kw_words) for k in keywords)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def dedupe_key(company: str, title: str, location: LocationInfo) -> str:
    company = re.sub(
        r"\b(pvt|private|ltd|limited|inc|llc|gmbh|corp|corporation)\b", "", _slug(company)
    )
    place = (location.cities or location.remote_regions or location.countries or [""])[0]
    basis = f"{' '.join(company.split())}|{_slug(title)}|{_slug(place)}|{location.remote_type}"
    return hashlib.sha256(basis.encode()).hexdigest()


def normalize(posting: RawPosting) -> NormalizedJob:
    title = " ".join(posting.title.split())[:300]
    company = " ".join(posting.company.split())[:200]
    description = posting.description_text.strip()
    location = parse_location(posting.location_text, title)
    salary = posting.salary or parse_salary(description)
    exp_min, exp_max = parse_experience(description)
    content_hash = hashlib.sha256(" ".join(description.lower().split()).encode()).hexdigest()
    return NormalizedJob(
        source=posting.source,
        source_job_id=posting.source_job_id,
        url=posting.url,
        title=title,
        company=company,
        location=location,
        employment_type=posting.employment_hint or detect_employment_type(title, description),
        salary=salary,
        experience_min_years=exp_min,
        experience_max_years=exp_max,
        description_text=description,
        content_hash=content_hash,
        dedupe_key=dedupe_key(company, title, location),
        posted_at=posting.posted_at,
        is_mock=posting.is_mock,
        raw=posting.raw,
    )
