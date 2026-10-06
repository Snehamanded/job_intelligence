from datetime import date

import pytest

from app.utils.dates import experience_months, parse_date_range
from app.utils.locations import normalize_location, normalize_locations

TODAY = date(2026, 10, 5)


@pytest.mark.parametrize(
    ("text", "start", "end", "months"),
    [
        ("Jul 2025 - Present", "2025-07", None, 16),
        ("January 2022 – Mar 2023", "2022-01", "2023-03", 15),
        ("01/2021 to 12/2021", "2021-01", "2021-12", 12),
        ("2024-07 - 2025-06", "2024-07", "2025-06", 12),
        ("Sept 2024 — Aug 2025", "2024-09", "2025-08", 12),
        ("Jul '23 - now", "2023-07", None, 40),
        ("2019 - 2023", "2019-01", "2023-01", 48),
        ("Software Engineer | Acme | Mar 2024 - Jun 2024", "2024-03", "2024-06", 4),
    ],
)
def test_parse_date_range(text: str, start: str, end: str | None, months: int) -> None:
    r = parse_date_range(text, TODAY)
    assert r is not None
    assert str(r.start) == start
    assert (str(r.end) if r.end else None) == end
    assert experience_months([r], TODAY) == months


@pytest.mark.parametrize(
    "text", ["Engineer", "", None, "2030 - 2031", "Dec 2024 - Jan 2024", "13/2020 - 01/2021"]
)
def test_unparseable_or_invalid_ranges(text: str | None) -> None:
    assert parse_date_range(text, TODAY) is None


def test_overlapping_roles_counted_once() -> None:
    a = parse_date_range("Jan 2023 - Dec 2023", TODAY)
    b = parse_date_range("Jun 2023 - Mar 2024", TODAY)
    gap = parse_date_range("Jan 2025 - Feb 2025", TODAY)
    assert a and b and gap
    assert experience_months([a, b], TODAY) == 15
    assert experience_months([a, b, gap], TODAY) == 17
    assert experience_months([], TODAY) == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bangalore", "Bengaluru"),
        ("bengaluru, Karnataka", "Bengaluru"),
        ("  new   delhi ", "Delhi"),
        ("Gurgaon", "Gurugram"),
        ("Bombay", "Mumbai"),
        ("san jose", "San Jose"),
        ("Remote", None),
        ("", None),
    ],
)
def test_normalize_location(raw: str, expected: str | None) -> None:
    assert normalize_location(raw) == expected


def test_normalize_locations_dedupes_and_drops_remote() -> None:
    assert normalize_locations(["Bangalore", "Bengaluru", "remote", "Pune", "poona"]) == [
        "Bengaluru",
        "Pune",
    ]
