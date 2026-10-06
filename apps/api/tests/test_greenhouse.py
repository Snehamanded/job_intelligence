import json

import httpx
import pytest

from app.connectors.base import ConnectorError, FetchReport, SearchQuery
from app.connectors.greenhouse import parse_job_url, valid_token
from app.services.jobs.normalize import normalize
from tests.conftest import GREENHOUSE_FIXTURES, fake_greenhouse, greenhouse_transport


def test_fetch_normalizes_real_payloads() -> None:
    requests: list[httpx.Request] = []
    gh = fake_greenhouse(greenhouse_transport(requests=requests))
    jobs = [normalize(p) for p in gh.fetch(SearchQuery([], ["groww", "gitlab"]), FetchReport())]

    by_title = {j.title: j for j in jobs}
    audit = by_title["Assistant Manager - Internal Audit"]
    assert (audit.company, audit.location.cities, audit.location.remote_type) == (
        "Groww",
        ["Bengaluru"],
        "onsite",
    )
    assert audit.source_job_id.startswith("groww:")
    assert audit.url and audit.url.startswith("https://")
    assert audit.posted_at is not None
    assert "<" not in audit.description_text and "About Groww" in audit.description_text

    assert by_title["Video Editor Intern"].employment_type == "internship"

    us = by_title["AI Transformation Owner, CRO"]
    assert (us.location.remote_type, us.location.remote_regions) == ("remote", ["United States"])
    assert us.salary is not None
    assert (us.salary.min, us.salary.max, us.salary.currency) == (139200, 235200, "USD")

    multi = by_title["Associate Renewals Manager"]
    assert multi.location.remote_regions == ["Canada", "United States"]

    assert {r.url.path for r in requests} == {"/v1/boards/groww/jobs", "/v1/boards/gitlab/jobs"}
    assert all(r.headers["user-agent"].startswith("JobIntelligence/") for r in requests)
    assert all(r.url.params["content"] == "true" for r in requests)


def test_one_failing_board_is_reported_not_fatal() -> None:
    gh = fake_greenhouse(greenhouse_transport(fail_boards=frozenset({"gitlab"})))
    report = FetchReport()
    postings = list(gh.fetch(SearchQuery([], ["gitlab", "groww", "nosuchboard"]), report))
    assert {p.company for p in postings} == {"Groww"}
    assert report.errors == ["gitlab: Greenhouse returned HTTP 500", "nosuchboard: Board not found"]


def test_all_boards_failing_raises() -> None:
    gh = fake_greenhouse(greenhouse_transport(fail_boards=frozenset({"gitlab"})))
    with pytest.raises(ConnectorError):
        list(gh.fetch(SearchQuery([], ["gitlab"]), FetchReport()))
    with pytest.raises(ConnectorError, match="No Greenhouse boards"):
        list(gh.fetch(SearchQuery([], []), FetchReport()))


def test_board_name_and_single_job() -> None:
    gh = fake_greenhouse()
    assert gh.board_name("groww") == "Groww"
    with pytest.raises(ConnectorError, match="Board not found"):
        gh.board_name("nosuchboard")
    with pytest.raises(ConnectorError, match="lowercase"):
        gh.board_name("../etc")
    job_id = json.loads((GREENHOUSE_FIXTURES / "groww_jobs.json").read_text())["jobs"][0]["id"]
    posting = gh.fetch_job("groww", str(job_id))
    assert posting.company == "Groww"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://job-boards.greenhouse.io/gitlab/jobs/8123456002", ("gitlab", "8123456002")),
        ("https://job-boards.eu.greenhouse.io/groww/jobs/4970739101", ("groww", "4970739101")),
        ("https://boards.greenhouse.io/Figma/jobs/123?gh_jid=123", ("figma", "123")),
        ("http://job-boards.greenhouse.io/gitlab/jobs/1", None),
        ("https://evil.example/greenhouse.io/gitlab/jobs/1", None),
        ("https://www.linkedin.com/jobs/view/123", None),
    ],
)
def test_parse_job_url(url: str, expected: tuple[str, str] | None) -> None:
    assert parse_job_url(url) == expected


def test_token_validation() -> None:
    assert valid_token("gitlab") and valid_token("my-company_1")
    assert not valid_token("") and not valid_token("a/b") and not valid_token("UPPER")


def test_real_network_is_blocked_in_tests() -> None:
    from app.connectors.registry import greenhouse
    from app.core.config import get_settings

    with pytest.raises(RuntimeError, match="Network access is disabled"):
        greenhouse(get_settings()).board_name("gitlab")
