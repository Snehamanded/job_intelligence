"""Mocks for Tier C sources (no public API, or terms restrict automated access).

They implement the connector interface with fictional, deterministic data so the pipeline can be
exercised end to end. They are off by default and every job they produce is marked as mock.
No scraping happens here or anywhere else.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

from app.connectors.base import FetchReport, SearchQuery, Tier
from app.services.jobs.normalize import RawPosting

_FICTIONAL = {
    "linkedin": [
        ("Backend Engineer", "Mock Fintech Co", "Bengaluru, India",
         "Build Python and FastAPI services. 1-3 years of experience. CTC: 12-18 LPA. Full-time."),
        ("Senior Data Engineer", "Mock Retail Labs", "Remote, India",
         "Own data pipelines in Airflow. 5+ years of experience required. Full-time."),
    ],
    "naukri": [
        ("Python Developer", "Mock Payments Pvt Ltd", "Hyderabad, India",
         "Django and PostgreSQL. Minimum 1 year of experience. "
         "Salary: ₹8,00,000 - ₹12,00,000 per annum."),
        ("Backend Engineer", "Mock Fintech Co", "Bengaluru, India",
         "Build Python and FastAPI services. 1-3 years of experience. CTC: 12-18 LPA. Full-time."),
    ],
    "indeed": [
        ("Software Engineer Intern", "Mock Health Startup", "Pune, India",
         "Internship for students. Stipend: ₹30,000 per month. This is a paid internship."),
    ],
}  # fmt: skip


class MockConnector:
    tier: Tier = "C"
    is_mock = True
    needs_targets = False

    def __init__(self, name: str, label: str) -> None:
        self.name = name
        self.label = label

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]:
        for i, (title, company, location, description) in enumerate(_FICTIONAL.get(self.name, [])):
            yield RawPosting(
                source=self.name,
                source_job_id=f"mock-{self.name}-{i}",
                title=title,
                company=company,
                location_text=location,
                description_text=description,
                url=None,
                posted_at=datetime(2026, 10, 1, tzinfo=UTC),
                is_mock=True,
            )
