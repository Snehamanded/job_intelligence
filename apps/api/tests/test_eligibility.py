from typing import Any

import pytest

from app.models import Job
from app.schemas.profile import Preferences
from app.services.jobs.eligibility import evaluate


def job(**overrides: Any) -> Job:
    base: dict[str, Any] = dict(
        title="Backend Engineer", company="Acme", cities=["Bengaluru"], countries=["India"],
        remote_type="onsite", remote_regions=[], employment_type="full_time",
        salary_min=1_200_000, salary_max=1_800_000, salary_currency="INR", salary_period="year",
        salary_unknown=False, experience_min_years=1,
    )  # fmt: skip
    base.update(overrides)
    return Job(**base)


PREFS = Preferences(
    remote_scope="india",
    onsite_locations=["Bengaluru"],
    open_to=["full_time"],
    min_salary=1_000_000,
    currency="INR",
)


def checks(j: Job, prefs: Preferences = PREFS, months: int | None = 22) -> dict[str, str]:
    return {c.name: c.status for c in evaluate(j, prefs, months).checks}


def test_matching_job_is_eligible() -> None:
    result = evaluate(job(), PREFS, 22)
    assert result.eligible
    assert {c.status for c in result.checks} == {"pass"}


@pytest.mark.parametrize(
    ("overrides", "check", "status"),
    [
        ({"employment_type": "internship"}, "employment_type", "fail"),
        ({"employment_type": "unknown"}, "employment_type", "unknown"),
        ({"cities": ["Mumbai"]}, "location", "fail"),
        ({"cities": [], "countries": ["India"]}, "location", "unknown"),
        ({"remote_type": "remote", "cities": [], "remote_regions": ["India"]}, "location", "pass"),
        ({"remote_type": "remote", "cities": [], "remote_regions": ["APAC"]}, "location", "fail"),
        (
            {"remote_type": "remote", "cities": [], "remote_regions": ["United States"]},
            "location",
            "fail",
        ),
        (
            {"remote_type": "remote", "cities": [], "remote_regions": ["Worldwide"]},
            "location",
            "fail",
        ),
        ({"remote_type": "remote", "cities": [], "remote_regions": []}, "location", "unknown"),
        ({"remote_type": "hybrid"}, "location", "pass"),
        ({"salary_max": 900_000}, "salary", "fail"),
        ({"salary_min": 80_000, "salary_max": 90_000, "salary_period": "month"}, "salary", "pass"),
        ({"salary_unknown": True, "salary_min": None, "salary_max": None}, "salary", "unknown"),
        ({"salary_currency": "USD"}, "salary", "unknown"),
        ({"experience_min_years": 5}, "experience", "fail"),
        ({"experience_min_years": 3}, "experience", "pass"),
        ({"experience_min_years": None}, "experience", "unknown"),
    ],
)
def test_individual_checks(overrides: dict[str, Any], check: str, status: str) -> None:
    assert checks(job(**overrides))[check] == status


def test_worldwide_scope_accepts_worldwide_remote() -> None:
    prefs = PREFS.model_copy(update={"remote_scope": "worldwide"})
    for region in ("Worldwide", "APAC", "India"):
        remote = job(remote_type="remote", cities=[], remote_regions=[region])
        assert checks(remote, prefs)["location"] == "pass", region
    us_only = job(remote_type="remote", cities=[], remote_regions=["United States"])
    assert checks(us_only, prefs)["location"] == "fail"  # remote, but not hiring in India


def test_no_remote_wanted() -> None:
    prefs = PREFS.model_copy(update={"remote_scope": "none"})
    remote = job(remote_type="remote", cities=[], remote_regions=["India"])
    assert checks(remote, prefs)["location"] == "fail"


def test_unknown_salary_policy_exclude_fails() -> None:
    prefs = PREFS.model_copy(update={"salary_unknown_policy": "exclude"})
    unknown = job(salary_unknown=True, salary_min=None, salary_max=None)
    assert checks(unknown, prefs)["salary"] == "fail"
    assert not evaluate(unknown, prefs, 22).eligible
    assert evaluate(unknown, PREFS, 22).eligible  # default policy is include


def test_no_preferences_never_fails_location_or_salary() -> None:
    result = evaluate(job(cities=["Mumbai"]), Preferences(), None)
    statuses = {c.name: c.status for c in result.checks}
    assert statuses["location"] == "unknown"
    assert statuses["salary"] == "pass"
    assert statuses["experience"] == "unknown"
    assert result.eligible
