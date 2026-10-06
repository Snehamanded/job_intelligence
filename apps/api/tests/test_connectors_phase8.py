import ipaddress
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

import app.connectors.lever as lever_module
from app.connectors.adzuna import AdzunaConnector
from app.connectors.base import ConnectorError, FetchReport, SearchQuery
from app.connectors.http import make_client
from app.connectors.jsonld import find_job_postings
from app.connectors.safe_http import UnsafeURLError, check_url
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import JobSourceConfig
from app.services.jobs.importer import restricted_site
from app.services.jobs.normalize import NormalizedJob, normalize
from tests.conftest import (
    CAREERS,
    SOURCES,
    fake_connectors,
    fake_resolve,
    greenhouse_transport,
    register,
)


def jobs_of(
    connector: Any, targets: list[str], keywords: list[str] | None = None
) -> list[NormalizedJob]:
    return [
        normalize(p) for p in connector.fetch(SearchQuery(keywords or [], targets), FetchReport())
    ]


# --- connectors on recorded payloads ---------------------------------------------------------


def test_lever() -> None:
    jobs = {j.title: j for j in jobs_of(fake_connectors().lever, ["palantir|Palantir"])}
    intern = jobs["Deployment Strategist, Internship"]
    assert (intern.company, intern.employment_type, intern.location.cities) == (
        "Palantir",
        "internship",
        ["Paris"],
    )
    london = jobs["Administrative Business Partner"]
    assert (london.location.remote_type, london.location.countries) == (
        "hybrid",
        ["United Kingdom"],
    )
    assert london.source_job_id.startswith("palantir:")
    assert london.url and london.url.startswith("https://jobs.lever.co/palantir/")
    assert london.posted_at is not None and len(london.description_text) > 200


def test_lever_pagination_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []
    lever = fake_connectors(greenhouse_transport(requests=requests)).lever
    monkeypatch.setattr(lever_module, "PAGE", 2)
    assert len(jobs_of(lever, ["palantir"])) == 3
    assert [r.url.params["skip"] for r in requests] == ["0", "2"]
    with pytest.raises(ConnectorError):
        list(lever.fetch(SearchQuery([], ["nosuchco"]), FetchReport()))


def test_ashby_respects_displayed_compensation() -> None:
    jobs = jobs_of(fake_connectors().ashby, ["ramp|Ramp"])
    shown = [j for j in jobs if j.raw.get("shouldDisplayCompensationOnJobPostings")]
    hidden = [j for j in jobs if not j.raw.get("shouldDisplayCompensationOnJobPostings")]
    assert shown and shown[0].salary is not None
    assert (shown[0].salary.min, shown[0].salary.max, shown[0].salary.currency) == (
        211400,
        290600,
        "USD",
    )
    assert hidden and all(j.salary is None for j in hidden)  # the employer chose not to show pay
    assert all(j.company == "Ramp" and j.employment_type == "full_time" for j in jobs)
    hybrid_and_remote = next(j for j in jobs if "Remote (Canada)" in j.location.display)
    assert {"Canada", "United States"} <= set(hybrid_and_remote.location.remote_regions)
    assert "New York" in hybrid_and_remote.location.cities
    london = next(j for j in jobs if j.title == "Account Executive")
    assert (london.location.remote_type, london.location.cities) == ("onsite", ["London"])


def test_remoteok_skips_legal_notice_and_parses_salary() -> None:
    jobs = jobs_of(fake_connectors().remoteok, ["*"])
    assert len(jobs) == 3 and all(j.location.remote_type == "remote" for j in jobs)
    paid = jobs[0].salary
    assert paid is not None and (paid.min, paid.max, paid.currency, paid.period) == (
        150000,
        185000,
        "USD",
        "year",
    )
    assert jobs[2].salary is None  # 0 means not listed
    assert all(j.url and j.url.startswith("https://remoteOK.com/") for j in jobs)


def test_remotive_regions_and_types() -> None:
    jobs = {j.title: j for j in jobs_of(fake_connectors().remotive, ["*"])}
    copywriter = jobs["Freelance Copywriter"]
    assert (
        copywriter.location.remote_regions == ["Worldwide"]
        and copywriter.employment_type == "contract"
    )
    assert copywriter.salary is not None and (copywriter.salary.min, copywriter.salary.max) == (
        20000,
        35000,
    )
    multi = jobs["Senior React Full-stack Developer"]
    assert {"Europe", "United States", "Canada", "APAC"} <= set(multi.location.remote_regions)


def test_adzuna_ignores_predicted_salary() -> None:
    adzuna = AdzunaConnector(
        make_client(get_settings(), greenhouse_transport()), app_id="id", app_key="key"
    )
    jobs = {j.title: j for j in jobs_of(adzuna, ["in"], ["Backend Engineer"])}
    real = jobs["Backend Engineer (Python)"]
    assert real.salary is not None
    assert (real.salary.min, real.salary.currency, real.location.cities) == (
        1200000,
        "INR",
        ["Bengaluru"],
    )
    assert jobs["Python Developer"].salary is None  # salary_is_predicted = 1: never guess
    assert real.employment_type == "full_time"


# --- import: SSRF guard, robots, JSON-LD -----------------------------------------------------


def _resolve_like_system(host: str) -> list[str]:
    """Literal and odd-form IPs resolve to the address they denote, like getaddrinfo."""
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    if host in ("2130706433", "0177.0.0.1"):
        return ["127.0.0.1"]
    return fake_resolve(host)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("ftp://careers.example.com/job", "Only http"),
        ("file:///etc/passwd", "Only http"),
        ("http://localhost/admin", "private or local"),
        ("http://127.0.0.1/", "private or local"),
        ("http://2130706433/", "private or local"),  # 127.0.0.1 as a decimal
        ("http://0177.0.0.1/", "private or local"),  # octal
        ("http://[::1]/", "private or local"),
        ("http://[::ffff:10.0.0.1]/", "private or local"),  # IPv4-mapped IPv6
        ("http://intranet.example/jobs", "private or local"),
        ("http://metadata.example/latest/meta-data", "private or local"),
        ("http://169.254.169.254/latest/meta-data", "private or local"),
        ("http://v6local.example/", "private or local"),
        ("https://careers.example.com:8443/job", "standard web ports"),
        ("https://user:pass@careers.example.com/job", "credentials"),
    ],
)
def test_unsafe_urls_rejected(url: str, message: str) -> None:
    with pytest.raises(UnsafeURLError, match=message):
        check_url(url, _resolve_like_system)


def test_public_url_allowed() -> None:
    assert check_url("https://careers.example.com/jobs/platform", fake_resolve)


def test_restricted_sites() -> None:
    assert restricted_site("https://www.linkedin.com/jobs/view/1") == "LinkedIn"
    assert restricted_site("https://in.indeed.com/viewjob?jk=1") == "Indeed"
    assert restricted_site("https://jobs.smartrecruiters.com/Acme/1") == "SmartRecruiters"
    assert restricted_site("https://notlinkedin.com/jobs") is None


def test_jsonld_parsing() -> None:
    jobs = find_job_postings((CAREERS / "job.html").read_text())
    assert len(jobs) == 1 and jobs[0]["title"] == "Platform Engineer"
    assert find_job_postings((CAREERS / "none.html").read_text()) == []
    assert find_job_postings("<script type='application/ld+json'>{not json</script>") == []


def _import(client: TestClient, headers: dict[str, str], url: str) -> Any:
    return client.post("/api/jobs/import", json={"url": url}, headers=headers)


def test_career_page_import(client: TestClient) -> None:
    headers = register(client)
    job = _import(client, headers, "https://careers.example.com/jobs/platform").json()
    assert (job["source"], job["title"], job["company"]) == (
        "careers",
        "Platform Engineer",
        "Example Corp",
    )
    assert (job["salary_min"], job["salary_max"], job["salary_currency"]) == (
        1500000,
        2400000,
        "INR",
    )
    assert (job["employment_type"], job["experience_min_years"]) == ("full_time", 2)
    assert job["locations"] == ["Bengaluru, India"]

    remote = _import(client, headers, "https://careers.example.com/jobs/remote").json()
    assert (remote["remote_type"], remote["remote_regions"], remote["employment_type"]) == (
        "remote",
        ["India"],
        "contract",
    )

    assert (
        _import(client, headers, "https://careers.example.com/moved").status_code == 201
    )  # re-checked redirect

    cases = {
        "https://careers.example.com/to-internal": "private or local",  # redirect to a private host
        "https://careers.example.com/private/job": "robots.txt",
        "https://careers.example.com/about": "standard format",
        "https://careers.example.com/file.pdf": "isn't a web page",
        "https://careers.example.com/missing": "wasn't found",
        "https://www.linkedin.com/jobs/view/123": "Paste the job description",
        "http://localhost:80/admin": "private or local",
    }
    for url, message in cases.items():
        resp = _import(client, headers, url)
        assert resp.status_code == 422 and message in resp.json()["detail"], (url, resp.json())


def test_lever_and_ashby_job_urls(client: TestClient) -> None:
    headers = register(client)
    lever_id = json.loads((SOURCES / "lever_palantir.json").read_text())[0]["id"]
    ashby_id = json.loads((SOURCES / "ashby_ramp.json").read_text())["jobs"][0]["id"]
    lever = _import(client, headers, f"https://jobs.lever.co/palantir/{lever_id}")
    assert lever.status_code == 201 and lever.json()["source"] == "lever"
    ashby = _import(client, headers, f"https://jobs.ashbyhq.com/ramp/{ashby_id}")
    assert ashby.status_code == 201 and ashby.json()["source"] == "ashby"


# --- source configuration, intervals, attribution --------------------------------------------


def _search(client: TestClient, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    run = client.post("/api/searches", json={"keywords": []}, headers=headers).json()
    results = client.get(f"/api/searches/{run['id']}").json()["source_results"]
    return {r["source"]: r for r in results}


def test_sources_config_and_rate_intervals(client: TestClient) -> None:
    headers = register(client)

    def add(body: dict[str, str]) -> Any:
        return client.post("/api/job-sources", json=body, headers=headers)

    assert (
        add({"source": "lever", "identifier": "palantir", "display_name": "Palantir"}).status_code
        == 201
    )
    assert add({"source": "ashby", "identifier": "ramp"}).json()["display_name"] == "Ramp"
    assert add({"source": "lever", "identifier": "nosuchco"}).status_code == 422
    assert add({"source": "remotive"}).status_code == 201
    assert add({"source": "remoteok"}).status_code == 201
    assert add({"source": "remoteok"}).status_code == 422  # already enabled
    adzuna = add({"source": "adzuna", "identifier": "in"})
    assert adzuna.status_code == 422 and "isn't configured" in adzuna.json()["detail"]

    results = _search(client, headers)
    assert results["lever"]["new"] == 3 and results["ashby"]["new"] >= 2
    assert results["remotive"]["new"] == 3 and results["remoteok"]["new"] == 3
    assert results["greenhouse"]["status"] == "skipped"

    # Searching again right away: Remotive and Remote OK are skipped, as they ask.
    results = _search(client, headers)
    assert (
        results["remotive"]["status"] == "skipped"
        and "next checked in" in results["remotive"]["error"]
    )
    assert results["remoteok"]["status"] == "skipped"
    assert results["lever"]["status"] == "completed"

    # After the interval, they run again.
    with get_sessionmaker()() as session:
        session.execute(
            update(JobSourceConfig).values(last_fetched_at=datetime.now(UTC) - timedelta(hours=7))
        )
        session.commit()
    assert _search(client, headers)["remotive"]["status"] == "completed"

    jobs = client.get("/api/jobs", params={"eligible_only": False, "source": "remoteok"}).json()[
        "items"
    ]
    assert jobs and all(j["source"] == "remoteok" for j in jobs)
    connectors = {c["name"]: c for c in client.get("/api/connectors").json()}
    assert (
        connectors["remoteok"]["config"] == "toggle"
        and "Remote OK" in connectors["remoteok"]["attribution"]
    )
    assert connectors["smartrecruiters"]["kind"] == "manual_only"
    assert connectors["adzuna"]["enabled"] is False


def test_same_description_in_different_cities_is_not_a_duplicate(client: TestClient) -> None:
    headers = register(client)
    description = "Help run our operations. " * 10

    def post(location: str, company: str = "Acme") -> Any:
        body = {
            "title": "Business Partner",
            "company": company,
            "location": location,
            "description": description,
        }
        return client.post("/api/jobs/import", json=body, headers=headers).json()

    nyc, london = post("New York, NY"), post("London, United Kingdom")
    assert nyc["id"] != london["id"]  # two openings
    again = post("New York, NY", company="Acme")
    assert again["id"] == nyc["id"]  # identical posting: same job
