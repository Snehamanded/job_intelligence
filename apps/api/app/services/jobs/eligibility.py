"""Deterministic eligibility of a job against the user's preferences (AGENTS.md section 6)."""

from dataclasses import dataclass, field
from typing import Literal

from app.models import Job
from app.schemas.profile import Preferences
from app.utils.locations import INDIA_REGIONS
from app.utils.salary import annualize

Status = Literal["pass", "fail", "unknown"]

# Allowed gap between a job's minimum years and the candidate's before it is ruled out.
EXPERIENCE_SLACK_YEARS = 2

_EMPLOYMENT_LABEL = {"full_time": "full-time", "contract": "contract", "internship": "internship",
                     "part_time": "part-time"}  # fmt: skip


@dataclass
class Check:
    name: Literal["employment_type", "location", "salary", "experience"]
    status: Status
    reason: str


@dataclass
class Eligibility:
    eligible: bool
    checks: list[Check] = field(default_factory=list)


def _employment(job: Job, prefs: Preferences) -> Check:
    if job.employment_type == "unknown":
        return Check("employment_type", "unknown", "Employment type not stated")
    label = _EMPLOYMENT_LABEL.get(job.employment_type, job.employment_type)
    if job.employment_type in prefs.open_to:
        return Check("employment_type", "pass", f"{label.capitalize()}, which you're open to")
    return Check(
        "employment_type", "fail", f"{label.capitalize()}; you're not open to {label} roles"
    )


def _location(job: Job, prefs: Preferences) -> Check:
    wanted = {c.lower() for c in prefs.onsite_locations}
    city_match = [c for c in job.cities if c.lower() in wanted]
    if job.remote_type == "remote":
        if prefs.remote_scope == "none":
            if city_match:
                return Check("location", "pass", f"In {city_match[0]}")
            return Check("location", "fail", "Remote role; you're not looking for remote work")
        # "india": remote roles open in India. "worldwide": also global/APAC remote roles.
        allowed = {"India"} if prefs.remote_scope == "india" else INDIA_REGIONS
        regions = set(job.remote_regions)
        if regions & allowed:
            return Check(
                "location", "pass", "Remote, open to " + ", ".join(sorted(regions & allowed))
            )
        if not regions:
            return Check("location", "unknown", "Remote, but the allowed countries aren't stated")
        return Check("location", "fail", "Remote only in " + ", ".join(job.remote_regions))
    if city_match:
        kind = "Hybrid" if job.remote_type == "hybrid" else "On-site"
        return Check("location", "pass", f"{kind} in {city_match[0]}")
    if not wanted and prefs.remote_scope == "none":
        return Check("location", "unknown", "Set your location preferences to check this")
    if not job.cities:
        where = ", ".join(job.countries) or "an unstated location"
        return Check("location", "unknown", f"City not stated ({where})")
    if not wanted:
        return Check(
            "location", "fail", f"On-site in {', '.join(job.cities)}; you only want remote"
        )
    return Check("location", "fail", f"In {', '.join(job.cities)}, not one of your cities")


def _salary(job: Job, prefs: Preferences) -> Check:
    if prefs.min_salary is None:
        return Check("salary", "pass", "No minimum salary set")
    unknown_status: Status = "fail" if prefs.salary_unknown_policy == "exclude" else "unknown"
    if job.salary_unknown or job.salary_currency is None or job.salary_period is None:
        return Check("salary", unknown_status, "Salary not listed")
    if job.salary_currency != prefs.currency:
        return Check(
            "salary", unknown_status,
            f"Salary is in {job.salary_currency}, not {prefs.currency}; not compared",
        )  # fmt: skip
    top = job.salary_max if job.salary_max is not None else job.salary_min
    if top is None:
        return Check("salary", unknown_status, "Salary not listed")
    yearly = annualize(top, job.salary_period)  # type: ignore[arg-type]
    if yearly < prefs.min_salary:
        return Check(
            "salary",
            "fail",
            f"Pays up to {yearly:,} {job.salary_currency}/year, below your minimum",
        )
    return Check("salary", "pass", "Meets your minimum salary")


def _experience(job: Job, experience_months: int | None) -> Check:
    if job.experience_min_years is None:
        return Check("experience", "unknown", "Experience requirement not stated")
    if experience_months is None:
        return Check(
            "experience",
            "unknown",
            f"Needs {job.experience_min_years}+ years; your experience is unknown",
        )
    years = experience_months / 12
    if job.experience_min_years - years > EXPERIENCE_SLACK_YEARS:
        return Check(
            "experience", "fail",
            f"Needs {job.experience_min_years}+ years; you have about {years:.1f}",
        )  # fmt: skip
    return Check(
        "experience", "pass", f"Needs {job.experience_min_years}+ years; you have about {years:.1f}"
    )


def evaluate(job: Job, prefs: Preferences, experience_months: int | None) -> Eligibility:
    checks = [
        _employment(job, prefs),
        _location(job, prefs),
        _salary(job, prefs),
        _experience(job, experience_months),
    ]
    return Eligibility(eligible=all(c.status != "fail" for c in checks), checks=checks)
