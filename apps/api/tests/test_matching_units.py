from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.schemas import JobMatchAssessment
from app.models import Job
from app.schemas.profile import Bullet, Experience, ProfileData, Project, Skill
from app.services.jobs.eligibility import Check, Eligibility
from app.services.matching import components as c
from app.services.matching.config import Bands, Ranking, ScoringSettings, Weights, label_for
from app.services.matching.refine import refine
from app.services.matching.skills import classify, find_skills, skills_score

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def job(**kw: Any) -> Job:
    base: dict[str, Any] = dict(title="Backend Engineer", experience_min_years=None,
                                experience_max_years=None, posted_at=None, priority=1)  # fmt: skip
    return Job(**{**base, **kw})


def profile() -> ProfileData:
    return ProfileData(
        skills=[Skill(name=n) for n in ("Python", "FastAPI", "PostgreSQL", "Docker")],
        experience=[
            Experience(
                title="Software Engineer",
                company="Acme",
                bullets=[Bullet(text="Built REST APIs in FastAPI with pytest coverage")],
            )
        ],
        projects=[Project(name="Job Tracker", technologies=["Django", "PostgreSQL"])],
    )


def test_skill_status_rules() -> None:
    pskills = c.profile_skill_map(profile())
    assert pskills["REST APIs"] == "REST APIs (in your experience)"  # from a verified bullet
    assert pskills["Unit Testing"] == "Unit Testing (in your experience)"  # "pytest" alias
    statuses = {m.name: (m.status, m.profile_skills) for m in classify(
        ["Python", "Django", "Flask", "Kubernetes", "Go", "REST APIs"], pskills)}  # fmt: skip
    assert statuses["Python"] == ("demonstrated", ["Python"])
    assert statuses["Django"] == ("demonstrated", ["Django"])  # project technology
    assert statuses["Flask"][0] == "related" and "FastAPI" in statuses["Flask"][1]
    assert statuses["Kubernetes"] == ("related", ["Docker"])
    assert statuses["Go"] == ("not_demonstrated", [])
    assert statuses["REST APIs"][0] == "demonstrated"


def test_skills_score() -> None:
    matches = classify(["Python", "Flask", "Go"], {"Python": "Python", "FastAPI": "FastAPI"})
    assert skills_score(matches) == 50  # (1 + 0.5 + 0) / 3
    assert skills_score([]) is None


def test_find_skills_precision() -> None:
    assert find_skills("We value people who Excel at teamwork and like to go fast") == []
    assert find_skills("Strong in Python, R, and SQL") == ["Python", "R", "SQL"]
    assert find_skills("Kubernetes (k8s) and AWS") == ["Kubernetes", "AWS"]


@pytest.mark.parametrize(
    ("min_y", "max_y", "months", "score"),
    [(None, None, 22, 70), (1, None, 22, 100), (3, None, 22, 65), (6, None, 22, 0),
     (1, 2, 120, 80), (2, None, None, 50)],
)  # fmt: skip
def test_experience_component(
    min_y: int | None, max_y: int | None, months: int | None, score: int
) -> None:
    assert (
        c.experience(job(experience_min_years=min_y, experience_max_years=max_y), months).score
        == score
    )


def test_role_component() -> None:
    data = profile()
    assert (
        c.role(job(title="Senior Back-End Developer"), ["Backend Engineer"], data, None).score
        == 100
    )
    assert c.role(job(title="Data Analyst"), ["Backend Engineer"], data, None).score == 0
    blended = c.role(job(title="Data Analyst"), ["Backend Engineer"], data, 80)
    assert (blended.score, blended.method) == (32, "embedding")
    assert c.role(job(title="X"), [], ProfileData(), None).method == "unknown"


def test_projects_component() -> None:
    assert c.projects_lexical(["Django", "PostgreSQL", "Go"], profile()).score == 80
    assert c.projects_lexical(["Go"], profile()).score == 20
    assert c.projects_lexical(["Go"], ProfileData()).score == 50


def test_freshness_and_salary_fit() -> None:
    assert c.freshness(job(posted_at=NOW - timedelta(days=3)), NOW) == 1.0
    assert c.freshness(job(posted_at=NOW - timedelta(days=60)), NOW) == 0.0
    assert c.freshness(job(posted_at=None), NOW) == 0.5
    assert 0.4 < c.freshness(job(posted_at=NOW - timedelta(days=33)), NOW) < 0.6

    def elig(status: Any) -> Eligibility:
        return Eligibility(True, [Check("salary", status, "")])

    assert c.salary_fit(elig("pass"), True) == 1.0
    assert c.salary_fit(elig("pass"), False) == 0.5
    assert c.salary_fit(elig("unknown"), True) == 0.5
    assert c.salary_fit(elig("fail"), True) == 0.0


def test_similarity_scaling() -> None:
    assert c.scale_similarity(0.66, 0.6, 0.9) == 20
    assert c.scale_similarity(0.5, 0.6, 0.9) == 0
    assert c.scale_similarity(0.95, 0.6, 0.9) == 100


def test_bands_and_config_validation() -> None:
    bands = Bands()
    assert [label_for(s, bands) for s in (95, 85, 75, 65, 10)] == [
        "Excellent", "Strong", "Good", "Moderate", "Weak"
    ]  # fmt: skip
    assert ScoringSettings().weights.skills == 30
    with pytest.raises(ValidationError):
        Weights(skills=0, experience=0, role=0, location=0, projects=0, industry=0, preferences=0)
    with pytest.raises(ValidationError):
        Ranking(match=0.9, freshness=0.2, salary_fit=0, user_priority=0)
    with pytest.raises(ValidationError):
        Bands(excellent=70, strong=80, good=60, moderate=50)


def test_llm_cannot_upgrade_skills_or_invent_projects() -> None:
    data = profile()
    pskills = c.profile_skill_map(data)
    code = classify(["Python", "Kubernetes", "Go", "Kafka"], pskills)
    assessment = JobMatchAssessment(
        skills=[
            {"name": "Python", "status": "not_demonstrated"},  # can't downgrade code's demonstrated
            {"name": "Kubernetes", "status": "not_demonstrated"},  # may downgrade related
            {"name": "Go", "status": "demonstrated", "profile_skill": "Go"},  # not in profile
            {"name": "Kafka", "status": "related", "profile_skill": "PostgreSQL"},  # real skill
            {"name": "Terraform", "status": "demonstrated", "profile_skill": "Docker"},
            {"name": "Rust", "status": "related", "profile_skill": "Python"},  # not in job text
        ],
        project_relevance=95,
        relevant_projects=["Imaginary Project"],
        industry_relevance=70,
        explanation="  Strong fit   for backend work. ",
    )
    job_text = "Python, Kubernetes, Go, Kafka and Terraform"
    refined = refine(assessment, code, pskills, data, job_text)
    statuses = {s.name: (s.status, s.profile_skills) for s in refined.skills}
    assert statuses["Python"] == ("demonstrated", ["Python"])
    assert statuses["Kubernetes"] == ("not_demonstrated", [])
    assert statuses["Go"] == ("not_demonstrated", [])
    assert statuses["Kafka"] == ("related", ["PostgreSQL"])
    assert statuses["Terraform"] == ("related", ["Docker"])  # never "demonstrated"
    assert "Rust" not in statuses
    assert refined.projects.score == 20  # high relevance without a real project isn't trusted
    assert refined.explanation == "Strong fit for backend work."

    real = refine(
        assessment.model_copy(update={"relevant_projects": ["job tracker"]}),
        code,
        pskills,
        data,
        job_text,
    )
    assert (real.projects.score, real.projects.detail) == (95, "Relevant: Job Tracker")


@pytest.mark.parametrize(
    ("title", "score"),
    [
        ("Staff Backend Engineer", 0),  # staff ~8 years, candidate ~1.8
        ("Senior Backend Engineer", 5),  # 5 years vs ~1.83: gap 3.17 -> 100 - 95
        ("Intermediate Backend Engineer, India", 95),  # gap 0.17
        ("Backend Engineer", 70),  # nothing stated or implied
        ("Software Engineering Intern", 100),
        ("Associate Renewals Manager", 70),  # "associate" is not a seniority signal here
        ("Engineering Manager - Git & Gitaly Operations", 0),
    ],
)
def test_experience_inferred_from_title(title: str, score: int) -> None:
    result = c.experience(job(title=title), 22)
    assert result.score == score
    if score not in (70,):
        assert "inferred" in result.detail or result.score == 100


def test_stated_years_beat_title() -> None:
    assert c.experience(job(title="Staff Engineer", experience_min_years=1), 22).score == 100


def test_embedding_retry_and_cache() -> None:
    import uuid as _uuid

    from app.ai.providers.base import AIProviderError
    from app.ai.providers.fake import FakeAIProvider
    from app.ai.services.embeddings import EmbeddingService
    from app.core.config import get_settings
    from app.core.db import get_sessionmaker
    from app.models import User

    class Flaky(FakeAIProvider):
        failures: int = 1

        def embed(self, texts: list[str], *, dims: int):  # type: ignore[no-untyped-def]
            if self.failures:
                self.failures -= 1
                raise AIProviderError("Gemini embedding error 429", retryable=True)
            return super().embed(texts, dims=dims)

    sleeps: list[float] = []
    with get_sessionmaker()() as session:
        user = User(email=f"{_uuid.uuid4().hex}@example.com", password_hash="x")
        session.add(user)
        session.commit()
        provider = Flaky()
        service = EmbeddingService(session, provider, get_settings(), sleep=sleeps.append)
        first = service.get_many(user.id, ["python backend", "data analyst"], "job")
        assert first is not None and len(first) == 2
        assert len(sleeps) == 1  # one 429, retried
        again = service.get_many(user.id, ["python backend", "data analyst", "go"], "job")
        assert again is not None
        for cached, original in zip(again[:2], first, strict=True):  # pgvector stores float32
            assert cached == pytest.approx(original, abs=1e-6)
        assert provider.embed_calls[-1] == ["go"]  # only the new text is embedded

        provider.failures = 10
        # Quota exhausted: cached vectors still come back, new ones are deferred (None).
        partial = service.get_many(user.id, ["python backend", "something new"], "job")
        assert partial is not None and partial[0] is not None and partial[1] is None
