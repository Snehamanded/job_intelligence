from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.connectors.base import ConnectorError, FetchReport, SearchQuery
from app.connectors.mock import MockConnector
from app.connectors.registry import describe
from app.connectors.rss import items
from app.core.config import get_settings
from app.services.jobs.importer import platform_of
from app.services.jobs.normalize import NormalizedJob, normalize
from tests.conftest import fake_connectors, register


def jobs_of(
    connector: Any, targets: list[str], keywords: list[str] | None = None
) -> list[NormalizedJob]:
    return [
        normalize(p) for p in connector.fetch(SearchQuery(keywords or [], targets), FetchReport())
    ]


def test_we_work_remotely() -> None:
    jobs = jobs_of(fake_connectors().weworkremotely, ["*"])
    first = jobs[0]
    assert (first.company, first.title) == ("Sezzle", "AML Compliance Analyst")  # "Company: Title"
    assert first.location.remote_regions == ["Worldwide"]
    assert all(j.location.remote_type == "remote" for j in jobs)
    assert all(j.url and j.url.startswith("https://weworkremotely.com/") for j in jobs)
    assert all(j.posted_at is not None for j in jobs)
    assert "<" not in first.description_text


def test_jobspresso() -> None:
    jobs = jobs_of(fake_connectors().jobspresso, ["*"])
    pm = jobs[0]
    assert (pm.title, pm.company) == ("Principal Product Manager, Conversational AI", "Hopper")
    assert pm.location.remote_type == "remote" and "Various US States" in " ".join(
        pm.location.display
    )
    assert jobs[1].title == "Senior Full Stack Engineer, Realtime & Voice"  # entities decoded


def test_himalayas() -> None:
    jobs = {
        (j.company, j.title): j
        for j in jobs_of(fake_connectors().himalayas, ["India"], ["backend engineer"])
    }
    drivetrain = jobs[("Drivetrain", "Backend Engineer")]
    assert drivetrain.location.remote_regions == ["India"] and drivetrain.salary is None
    clera = jobs[("Clera", "Backend Engineer")]
    assert clera.salary is not None and (
        clera.salary.min,
        clera.salary.currency,
        clera.salary.period,
    ) == (116000, "EUR", "year")
    assert clera.location.remote_regions == ["Worldwide"]


@pytest.mark.parametrize(
    "xml",
    [
        # Entity expansion ("billion laughs")
        '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        "<rss><channel><item><title>&b;</title></item></channel></rss>",
        # External entity (XXE)
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        "<rss><channel><item><title>&e;</title></item></channel></rss>",
        "not xml at all",
    ],
)
def test_untrusted_feeds_are_parsed_safely(xml: str) -> None:
    with pytest.raises(ConnectorError, match="couldn't be read safely"):
        items(xml, "Feed")


def test_every_requested_source_is_listed() -> None:
    infos = {i.name: i for i in describe(get_settings())}
    expected = {
        "general": {"linkedin", "indeed", "glassdoor", "ziprecruiter", "google_jobs"},
        "india": {"naukri", "foundit", "shine", "apna"},
        "startup": {"wellfound", "instahyre", "cutshort", "hirist"},
        "remote": {"remoteok", "weworkremotely", "remotive", "himalayas", "jobspresso"},
        "ats": {"greenhouse", "lever", "ashby", "workday", "smartrecruiters", "icims", "taleo",
                "successfactors"},
    }  # fmt: skip
    for category, names in expected.items():
        for name in names:
            assert infos[name].category == category, name
    live = {n for n, i in infos.items() if i.kind == "real"}
    assert {
        "greenhouse",
        "lever",
        "ashby",
        "remoteok",
        "weworkremotely",
        "remotive",
        "himalayas",
        "jobspresso",
    } <= live
    assert all(
        infos[n].kind == "mock"
        for n in expected["india"] | expected["startup"] | {"linkedin", "indeed"}
    )
    assert all(
        infos[n].kind == "import"
        for n in ("workday", "icims", "taleo", "successfactors", "google_jobs")
    )


def test_tier_c_mocks_are_fictional_and_labeled() -> None:
    for name, label in (("naukri", "Naukri"), ("wellfound", "Wellfound"), ("shine", "Shine")):
        jobs = list(MockConnector(name, label).fetch(SearchQuery([], []), FetchReport()))
        assert jobs and all(j.is_mock and j.source == name and j.url is None for j in jobs)


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        (
            "https://acme.wd5.myworkdayjobs.com/en-US/External/job/Bengaluru/Engineer_R123",
            "workday",
        ),
        ("https://jobs.smartrecruiters.com/Acme/7430000000000-engineer", "smartrecruiters"),
        ("https://careers-acme.icims.com/jobs/1234/engineer/job", "icims"),
        ("https://acme.taleo.net/careersection/2/jobdetail.ftl?job=1", "taleo"),
        ("https://career5.successfactors.com/career?company=acme", "successfactors"),
        ("https://careers.example.com/jobs/platform", "careers"),
    ],
)
def test_platform_labels(url: str, platform: str) -> None:
    assert platform_of(url) == platform


def test_workday_page_import_is_labeled(client: TestClient) -> None:
    headers = register(client)
    url = "https://acme.wd5.myworkdayjobs.com/en-US/External/job/Bengaluru/Platform-Engineer_R1"
    job = client.post("/api/jobs/import", json={"url": url}, headers=headers).json()
    assert (job["source"], job["title"]) == ("workday", "Platform Engineer")


def test_new_feeds_in_a_search(client: TestClient) -> None:
    headers = register(client)
    for source in ("weworkremotely", "jobspresso", "himalayas"):
        assert (
            client.post("/api/job-sources", json={"source": source}, headers=headers).status_code
            == 201
        )
    himalayas = next(s for s in client.get("/api/job-sources").json() if s["source"] == "himalayas")
    assert himalayas["identifier"] == "India"
    run = client.post("/api/searches", json={"keywords": []}, headers=headers).json()
    results = {
        r["source"]: r for r in client.get(f"/api/searches/{run['id']}").json()["source_results"]
    }
    assert results["weworkremotely"]["new"] == 3 and results["jobspresso"]["new"] == 3
    assert results["himalayas"]["status"] == "completed" and results["himalayas"]["new"] >= 1


def test_default_sources_switched_on_at_first_use(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "default_sources_enabled", True)
    monkeypatch.setattr(
        get_settings(), "starter_company_boards", "greenhouse:acme:Acme,bogus:x,lever:palantir"
    )
    headers = register(client)
    sources = client.get("/api/job-sources").json()
    assert {(s["source"], s["identifier"], s["display_name"]) for s in sources} >= {
        ("greenhouse", "acme", "Acme"), ("lever", "palantir", "Palantir"),
        ("remoteok", "*", "remoteok"), ("himalayas", "India", "himalayas"),
    }  # fmt: skip
    assert len(sources) == 7  # five feeds + two valid boards; "bogus" ignored

    # Switching a feed off keeps it off: defaults are not re-applied.
    wwr = next(s for s in sources if s["source"] == "weworkremotely")
    assert client.delete(f"/api/job-sources/{wwr['id']}", headers=headers).status_code == 204
    run = client.post("/api/searches", json={"keywords": []}, headers=headers).json()
    results = {
        r["source"]: r for r in client.get(f"/api/searches/{run['id']}").json()["source_results"]
    }
    assert results["weworkremotely"]["status"] == "skipped"
    assert results["jobspresso"]["new"] == 3 and results["greenhouse"]["status"] != "skipped"
    again = client.post("/api/job-sources", json={"source": "weworkremotely"}, headers=headers)
    assert again.status_code == 201 and again.json()["enabled"] is True
    assert len(client.get("/api/job-sources").json()) == 7


def test_job_cap_is_per_board() -> None:
    from app.connectors.base import FetchReport, SearchQuery
    from app.connectors.registry import build
    from app.core.config import get_settings
    from tests.conftest import greenhouse_transport

    settings = get_settings().model_copy(
        update={"connector_request_delay_seconds": 0, "max_jobs_per_source": 1}
    )
    connector = build(settings, greenhouse_transport()).greenhouse
    postings = list(connector.fetch(SearchQuery([], ["groww", "gitlab"]), FetchReport()))
    assert [p.company for p in postings] == ["Groww", "GitLab"]
