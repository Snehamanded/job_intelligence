import re

"""Location normalization for preferences (and later, job postings)."""

_ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "blr": "Bengaluru",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "navi mumbai": "Navi Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi NCR",
    "delhi ncr": "Delhi NCR",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "noida": "Noida",
    "madras": "Chennai",
    "chennai": "Chennai",
    "calcutta": "Kolkata",
    "kolkata": "Kolkata",
    "poona": "Pune",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "secunderabad": "Hyderabad",
    "trivandrum": "Thiruvananthapuram",
    "thiruvananthapuram": "Thiruvananthapuram",
    "cochin": "Kochi",
    "kochi": "Kochi",
    "mysore": "Mysuru",
    "mysuru": "Mysuru",
    "baroda": "Vadodara",
    "vadodara": "Vadodara",
    "nyc": "New York",
    "new york city": "New York",
    "sf": "San Francisco",
    "bay area": "San Francisco Bay Area",
}

# Remote is a separate preference (remote_scope), not a place.
_NOT_PLACES = {"remote", "anywhere", "wfh", "work from home", "hybrid"}


def normalize_location(raw: str) -> str | None:
    """Canonical city name, or None if the value is empty or not a place."""
    cleaned = " ".join(raw.replace(",", " , ").split()).strip(" ,")
    if not cleaned:
        return None
    city = cleaned.split(",")[0].strip()
    key = city.lower().rstrip(".")
    if key in _NOT_PLACES:
        return None
    if key in _ALIASES:
        return _ALIASES[key]
    return " ".join(word if word.isupper() else word.capitalize() for word in city.split())


def normalize_locations(values: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        normalized = normalize_location(value)
        if normalized and normalized.lower() not in seen:
            seen[normalized.lower()] = normalized
    return list(seen.values())


COUNTRIES = {
    "india": "India", "bharat": "India",
    "united states": "United States", "united states of america": "United States",
    "usa": "United States", "us": "United States", "u.s.": "United States",
    "u.s.a.": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "england": "United Kingdom",
    "canada": "Canada", "germany": "Germany", "france": "France", "spain": "Spain",
    "netherlands": "Netherlands", "ireland": "Ireland", "poland": "Poland", "portugal": "Portugal",
    "singapore": "Singapore", "japan": "Japan", "australia": "Australia", "brazil": "Brazil",
    "mexico": "Mexico", "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "israel": "Israel", "switzerland": "Switzerland", "sweden": "Sweden", "italy": "Italy",
}  # fmt: skip
REGIONS = {
    "worldwide": "Worldwide", "anywhere": "Worldwide", "global": "Worldwide",
    "emea": "EMEA", "apac": "APAC", "asia": "APAC", "americas": "Americas",
    "north america": "Americas", "latam": "Americas", "europe": "Europe", "eu": "Europe",
}  # fmt: skip
# Remote regions an India-based candidate can work from.
INDIA_REGIONS = {"India", "Worldwide", "APAC"}

INDIAN_CITIES = {
    "Bengaluru", "Mumbai", "Navi Mumbai", "Delhi", "Delhi NCR", "Gurugram", "Noida", "Chennai",
    "Kolkata", "Pune", "Hyderabad", "Thiruvananthapuram", "Kochi", "Mysuru", "Vadodara",
    "Ahmedabad", "Jaipur", "Chandigarh", "Indore", "Coimbatore", "Bhubaneswar", "Lucknow",
}  # fmt: skip


def normalize_country(raw: str) -> str | None:
    key = " ".join(raw.lower().replace(".", ". ").split()).replace(". ", ".").strip(" .,")
    return COUNTRIES.get(key) or COUNTRIES.get(key.replace(".", ""))


def normalize_region(raw: str) -> str | None:
    key = " ".join(raw.lower().split()).strip(" .,")
    return normalize_country(key) or REGIONS.get(key)


def canonical_city(raw: str) -> str | None:
    """Known city name from strings like "Bengaluru-VTP" or "Bangalore Office"."""
    cleaned = " ".join(raw.split()).strip(" ,.-")
    direct = _ALIASES.get(cleaned.lower())
    if direct:
        return direct
    head = re.split(r"\s*[-–(/]\s*|\s+office\b|\s+hq\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[
        0
    ]
    return _ALIASES.get(head.lower().strip())
