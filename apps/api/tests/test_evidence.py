import json
from datetime import date

from app.ai.schemas import ResumeExtraction
from app.services.resume.evidence import (
    EvidenceValidator,
    profile_experience_months,
    skill_supported,
)
from app.services.resume.heuristic import heuristic_extract
from app.utils.text import TextIndex, normalize_text
from tests.helpers import ai_fixture, fixture_text

TODAY = date(2026, 10, 5)


def _sneha() -> str:
    return normalize_text(fixture_text("sneha_backend.txt"))


def test_text_index_finds_quotes_and_maps_to_original_offsets() -> None:
    text = normalize_text("Intro\n• Built   REST APIs – using FastAPI\nEnd")
    index = TextIndex(text)
    span = index.find("built rest apis - using fastapi")
    assert span is not None
    assert text[span[0] : span[1]] == "Built REST APIs – using FastAPI"
    assert index.find("• Built REST APIs") is not None
    assert index.find("Built GraphQL APIs") is None
    assert index.find("   ") is None


def test_skill_support_uses_word_boundaries_and_aliases() -> None:
    assert skill_supported("Python", "Languages: Python, SQL")
    assert skill_supported("Amazon Web Services", "Tools: Git, AWS")
    assert skill_supported("JS", "JavaScript and HTML")
    assert skill_supported("javascript", "Frontend in JS")
    assert not skill_supported("Go", "Google Analytics")
    assert not skill_supported("R", "React developer")
    assert not skill_supported("Kubernetes", "Docker")


def test_llm_extraction_keeps_supported_and_flags_invented_claims() -> None:
    text = _sneha()
    extraction = ResumeExtraction.model_validate_json(
        ai_fixture("sneha_backend.invented_claims.json")
    )
    data = EvidenceValidator(text, TODAY).validate(extraction)

    skills = {s.name for s in data.skills}
    assert {"Python", "FastAPI", "Amazon Web Services", "pytest"} <= skills
    assert "Kubernetes" not in skills  # quote is not in the resume
    assert "Go" not in skills  # quote is real but doesn't mention Go

    acme = data.experience[0]
    assert [b.text for b in acme.bullets][:3] == [
        "Built REST APIs in FastAPI serving 2,000 daily users",
        "Reduced report generation time by 40% by adding PostgreSQL indexes",
        "Wrote unit tests with pytest and set up GitHub Actions CI",
    ]
    assert all("Led a team" not in b.text for b in acme.bullets)
    assert (acme.start, acme.end, acme.is_current) == ("2025-07", None, True)

    project = data.projects[0]
    assert project.technologies == ["Django", "PostgreSQL", "Docker"]  # Redis is not in the resume
    assert data.education[0].degree == "B.E."
    assert data.education[0].field_of_study == "Computer Science"
    assert data.certifications[0].issuer == "AWS"

    unsupported = {(u.kind, u.label, u.reason) for u in data.unsupported}
    assert ("skill", "Kubernetes", "Quoted text was not found in the resume") in unsupported
    assert ("skill", "Go", "The quoted text does not mention it") in unsupported
    assert any(u.kind == "bullet" and "Led a team" in u.label for u in data.unsupported)
    assert any(u.kind == "skill" and u.label.startswith("Redis") for u in data.unsupported)
    assert profile_experience_months(data, TODAY) == 22


def test_every_kept_item_has_a_span_pointing_at_its_quote() -> None:
    text = _sneha()
    extraction = ResumeExtraction.model_validate_json(
        ai_fixture("sneha_backend.invented_claims.json")
    )
    data = EvidenceValidator(text, TODAY).validate(extraction)
    items = [*data.skills, *data.experience, *data.projects, *data.education, *data.certifications]
    items += [b for e in data.experience for b in e.bullets]
    assert items
    for item in items:
        assert item.source == "resume"
        assert item.source_span is not None
        assert item.evidence is not None
        quoted = text[item.source_span.start : item.source_span.end]
        assert TextIndex.fold(quoted) == TextIndex.fold(item.evidence.lstrip("•").strip())


def test_title_or_company_not_in_quote_is_rejected() -> None:
    text = _sneha()
    raw = json.loads(ai_fixture("sneha_backend.invented_claims.json"))
    raw["experience"][0]["title"] = "Senior Staff Engineer"
    raw["contact"] = None
    raw["email"] = "someone.else@example.com"
    data = EvidenceValidator(text, TODAY).validate(ResumeExtraction.model_validate(raw))
    assert [e.title for e in data.experience] == ["Software Engineering Intern"]
    assert data.contact.email is None
    assert any(u.kind == "experience" for u in data.unsupported)
    assert any(u.kind == "contact" for u in data.unsupported)


def test_heuristic_parser_on_two_layouts() -> None:
    sneha = EvidenceValidator(_sneha(), TODAY).validate(heuristic_extract(_sneha()))
    assert sneha.contact.name == "Sneha Rao"
    assert sneha.contact.email == "sneha.rao@example.com"
    assert [s.name for s in sneha.skills][:3] == ["Python", "JavaScript", "SQL"]
    assert [(e.title, e.company) for e in sneha.experience] == [
        ("Software Engineer", "Acme Analytics Pvt Ltd"),
        ("Software Engineering Intern", "Nimbus Labs"),
    ]
    assert len(sneha.experience[0].bullets) == 3
    assert sneha.education[0].degree == "B.E"
    assert sneha.unsupported == []

    arjun_text = normalize_text(fixture_text("arjun_data.txt"))
    arjun = EvidenceValidator(arjun_text, TODAY).validate(heuristic_extract(arjun_text))
    assert arjun.contact.name == "Arjun Mehta"
    assert "Power BI" in {s.name for s in arjun.skills}
    assert [(e.title, e.company, e.start, e.end) for e in arjun.experience] == [
        ("Data Analyst", "Brightline Retail", "2023-03", None),
        ("Junior Data Analyst", "Orbit Finance", "2021-06", "2023-02"),
    ]
    assert profile_experience_months(arjun, TODAY) == 65
    assert arjun.education[0].institution == "Savitribai Phule Pune University"


def test_project_details_supported_only_within_the_projects_own_block() -> None:
    text = normalize_text(
        "Projects\n"
        "Job Tracker - personal tracker\n"
        "• Built with Django and PostgreSQL\n"
        "Chat App\n"
        "• Realtime chat using Redis\n"
        "Skills\n"
        "Kafka"
    )
    extraction = ResumeExtraction.model_validate(
        {
            "projects": [
                {
                    "name": "Job Tracker",
                    "evidence": "Job Tracker - personal tracker",
                    "technologies": ["Django", "PostgreSQL", "Redis"],
                },
                {
                    "name": "Chat App",
                    "evidence": "Chat App",
                    "technologies": ["Redis", "Kafka"],
                },
            ]
        }
    )
    data = EvidenceValidator(text, TODAY).validate(extraction)
    assert data.projects[0].technologies == ["Django", "PostgreSQL"]  # Redis belongs to Chat App
    assert data.projects[1].technologies == ["Redis"]  # Kafka is past the Skills heading
    labels = {u.label for u in data.unsupported}
    assert labels == {"Redis (in project Job Tracker)", "Kafka (in project Chat App)"}


def test_education_details_on_the_next_line_are_supported() -> None:
    text = normalize_text(
        "Education\nRV College of Engineering, Bengaluru\nB.E. in Computer Science, 2021 - 2025\n"
        "Certifications\nB.Sc. Physics"
    )
    extraction = ResumeExtraction.model_validate(
        {
            "education": [
                {
                    "institution": "RV College of Engineering",
                    "degree": "B.E.",
                    "field_of_study": "Computer Science",
                    "date_text": "2021 - 2025",
                    "evidence": "RV College of Engineering, Bengaluru",
                },
                {
                    "institution": "RV College of Engineering",
                    "degree": "B.Sc.",
                    "evidence": "RV College of Engineering, Bengaluru",
                },
            ]
        }
    )
    data = EvidenceValidator(text, TODAY).validate(extraction)
    edu = data.education[0]
    assert (edu.degree, edu.field_of_study, edu.start) == ("B.E.", "Computer Science", "2021-01")
    assert data.education[1].degree is None  # "B.Sc." is only under Certifications


def test_recorded_gemini_responses_verify_cleanly() -> None:
    """Real responses recorded from Gemini (prompt v2) on the fictional resumes."""
    expected = {
        "sneha_backend": (10, ["Acme Analytics Pvt Ltd", "Nimbus Labs"], 22),
        "arjun_data": (7, ["Brightline Retail", "Orbit Finance"], 65),
    }
    for name, (skills, companies, months) in expected.items():
        text = normalize_text(fixture_text(f"{name}.txt"))
        extraction = ResumeExtraction.model_validate_json(ai_fixture(f"{name}.gemini.json"))
        data = EvidenceValidator(text, TODAY).validate(extraction)
        assert data.unsupported == [], name
        assert len(data.skills) == skills, name
        assert [e.company for e in data.experience] == companies, name
        assert profile_experience_months(data, TODAY) == months, name
