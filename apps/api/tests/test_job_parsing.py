import pytest

from app.services.jobs.normalize import (
    detect_employment_type,
    parse_location,
    title_matches,
)
from app.utils.experience import parse_experience
from app.utils.html_text import html_to_text
from app.utils.salary import annualize, parse_salary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("United States Salary Range $139,200 — $235,200 USD", (139200, 235200, "USD", "year")),
        ("Germany Annual Pay Range €71.000 — €84.000 EUR", (71000, 84000, "EUR", "year")),
        ("United Kingdom Annual Pay Range £46,000 — £54,000 GBP", (46000, 54000, "GBP", "year")),
        ("CTC: 12-18 LPA", (1200000, 1800000, "INR", "year")),
        ("Compensation ₹12,00,000 - ₹18,00,000 per annum", (1200000, 1800000, "INR", "year")),
        ("Stipend: ₹25,000 per month", (25000, None, "INR", "month")),
        ("Salary: $45/hour", (45, None, "USD", "hour")),
        ("Salary: $120k–$150k", (120000, 150000, "USD", "year")),
        ("Salary: up to INR 15 lakhs", (None, 1500000, "INR", "year")),
        ("Package: 1.2 Cr per annum", (12000000, None, "INR", "year")),
    ],
)
def test_parse_salary(text: str, expected: tuple[object, ...]) -> None:
    s = parse_salary(text)
    assert s is not None
    assert (s.min, s.max, s.currency, s.period) == expected


@pytest.mark.parametrize(
    "text",
    [
        "We raised $50 million in funding",  # no salary context
        "Salary: 50,000",  # no currency: never guess
        "Salary: ₹50,000",  # INR without period, too small to be clearly annual
        "Salary: competitive",
        "Salary: $90 - $40",  # inverted range
        "",
    ],
)
def test_salary_unknown_is_never_guessed(text: str) -> None:
    assert parse_salary(text) is None


def test_annualize() -> None:
    assert annualize(25000, "month") == 300000
    assert annualize(50, "hour") == 104000


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3+ years of experience in sales", (3, None)),
        ("8-12 years of progressive experience", (8, 12)),
        ("1–2 years of experience in operations", (1, 2)),
        ("Minimum 2years post-qualification experience", (2, None)),
        ("Experience: 2 to 4 yrs", (2, 4)),
        ("You have 3 years of hands-on experience", (3, None)),
        ("We are a 5 year old company. Experience with Python is a plus.", (None, None)),
        ("Join our 10 year journey", (None, None)),
    ],
)
def test_parse_experience(text: str, expected: tuple[int | None, int | None]) -> None:
    assert parse_experience(text) == expected


def test_html_to_text() -> None:
    raw = (
        "&lt;h2&gt;About&lt;/h2&gt;&lt;p&gt;We build &amp;amp; ship.&lt;/p&gt;"
        "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;SQL&lt;/li&gt;&lt;/ul&gt;"
        "&lt;script&gt;alert(1)&lt;/script&gt;"
    )
    text = html_to_text(raw, double_escaped=True)
    assert text == "About\n\nWe build & ship.\n\n• Python\n• SQL"
    assert "alert" not in text and "<" not in text


@pytest.mark.parametrize(
    ("location", "title", "remote_type", "cities", "regions"),
    [
        ("Bengaluru-VTP, India", "", "onsite", ["Bengaluru"], []),
        ("Bangalore, India", "", "onsite", ["Bengaluru"], []),
        ("Remote, Canada; Remote, US", "", "remote", [], ["Canada", "United States"]),
        ("Remote - USA", "", "remote", [], ["United States"]),
        ("Remote", "", "remote", [], []),
        ("Remote, India", "", "remote", [], ["India"]),
        ("Hybrid - Pune", "", "hybrid", ["Pune"], []),
        ("Mumbai, India; Remote, India", "", "remote", ["Mumbai"], ["India"]),
        ("India", "", "onsite", [], []),
        ("", "Backend Engineer (Remote)", "remote", [], []),
        ("", "", "unknown", [], []),
    ],
)
def test_parse_location(
    location: str, title: str, remote_type: str, cities: list[str], regions: list[str]
) -> None:
    info = parse_location(location, title)
    assert (info.remote_type, info.cities, info.remote_regions) == (remote_type, cities, regions)


def test_parse_location_infers_india_from_city_and_labels_remote() -> None:
    info = parse_location("Hyderabad; Remote, Canada; Remote, US")
    assert info.countries == ["India"]
    assert info.display == ["Hyderabad, India", "Remote (Canada)", "Remote (United States)"]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Video Editor Intern", "", "internship"),
        ("YouTube & Content - Internship", "", "internship"),
        ("Data Engineer (Contract)", "", "contract"),
        ("Part-time Tutor", "", "part_time"),
        ("Backend Engineer", "This is a full-time role.", "full_time"),
        ("Backend Engineer", "Great team.", "unknown"),
        ("Internal Audit Manager", "", "unknown"),  # "Internal" is not "intern"
    ],
)
def test_employment_type(title: str, description: str, expected: str) -> None:
    assert detect_employment_type(title, description) == expected


def test_title_matching() -> None:
    assert title_matches("Senior Back-End Developer, Payments", ["Backend Engineer"])
    assert title_matches("Sr. Python Developer", ["python engineer"])
    assert title_matches("Anything", [])
    assert not title_matches("Backend Engineer", ["Frontend Engineer"])
    assert not title_matches("Video Editor Intern", ["Backend Engineer", "Data Analyst"])
    assert title_matches("Data Analyst II", ["Backend Engineer", "Data Analyst"])
