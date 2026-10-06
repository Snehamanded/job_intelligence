"""Skill detection in job text and demonstrated/related/not_demonstrated labels, in code.

`demonstrated` means the skill (or an alias) is among the verified profile skills. `related`
means a verified profile skill is in the same family. Related is never shown as demonstrated.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

SkillStatus = Literal["demonstrated", "related", "not_demonstrated"]

# canonical name -> aliases (lowercase). Canonical names are what the UI shows.
VOCABULARY: dict[str, list[str]] = {
    "Python": ["python", "python3"], "Java": ["java"], "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript", "ts"], "Go": ["golang", "go lang"], "Rust": ["rust"],
    "C++": ["c++", "cpp"], "C#": ["c#", "csharp", ".net", "dotnet"], "Ruby": ["ruby"],
    "PHP": ["php"], "Kotlin": ["kotlin"], "Swift": ["swift"], "Scala": ["scala"], "R": ["r"],
    "SQL": ["sql"], "Bash": ["bash", "shell scripting"],
    "FastAPI": ["fastapi"], "Django": ["django"], "Flask": ["flask"],
    "Spring": ["spring", "spring boot"],
    "Node.js": ["node.js", "nodejs", "node"], "Express": ["express", "express.js"],
    "Ruby on Rails": ["rails", "ruby on rails"], "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"], "Vue": ["vue", "vue.js"], "Angular": ["angular"],
    "HTML": ["html", "html5"], "CSS": ["css", "css3", "tailwind", "sass"],
    "GraphQL": ["graphql"], "REST APIs": ["rest api", "rest apis", "restful", "rest"],
    "gRPC": ["grpc"], "Microservices": ["microservices", "microservice"],
    "PostgreSQL": ["postgresql", "postgres"], "MySQL": ["mysql"], "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"], "Elasticsearch": ["elasticsearch", "opensearch"], "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"], "Snowflake": ["snowflake"], "BigQuery": ["bigquery"],
    "AWS": ["aws", "amazon web services"], "GCP": ["gcp", "google cloud"], "Azure": ["azure"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"], "CI/CD": ["ci/cd", "continuous integration", "github actions",
    "jenkins", "gitlab ci"], "Git": ["git"], "Linux": ["linux", "unix"],
    "Machine Learning": ["machine learning", "ml"], "Deep Learning": ["deep learning"],
    "NLP": ["nlp", "natural language processing"], "LLMs": ["llm", "llms", "large language models",
    "generative ai", "genai"], "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"],
    "scikit-learn": ["scikit-learn", "sklearn"], "Pandas": ["pandas"], "NumPy": ["numpy"],
    "Spark": ["spark", "pyspark"], "Airflow": ["airflow"], "dbt": ["dbt"], "ETL": ["etl", "elt"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Statistics": ["statistics", "statistical analysis"],
    "Excel": ["excel", "spreadsheets"], "Power BI": ["power bi", "powerbi"], "Tableau": ["tableau"],
    "Looker": ["looker"], "A/B Testing": ["a/b testing", "experimentation"],
    "Unit Testing": ["unit testing", "unit tests", "pytest", "jest", "junit", "tdd"],
    "Selenium": ["selenium", "playwright", "cypress"], "Figma": ["figma"],
    "Android": ["android"], "iOS": ["ios"], "React Native": ["react native"],
    "Flutter": ["flutter"],
    "Salesforce": ["salesforce"], "SEO": ["seo"], "Agile": ["agile", "scrum"],
    "Application Security": ["application security", "appsec", "owasp"], "TCP/IP": ["tcp/ip"],
}  # fmt: skip

# Families of interchangeable or closely related skills.
RELATED_GROUPS: list[set[str]] = [
    {"FastAPI", "Django", "Flask", "Spring", "Express", "Ruby on Rails", "Node.js"},
    {"React", "Vue", "Angular", "Next.js", "React Native"},
    {"JavaScript", "TypeScript", "Node.js"},
    {"PostgreSQL", "MySQL", "SQL", "Snowflake", "BigQuery"},
    {"MongoDB", "Redis", "Elasticsearch"},
    {"AWS", "GCP", "Azure"},
    {"Docker", "Kubernetes", "Terraform", "CI/CD"},
    {"Kafka", "RabbitMQ"},
    {"Power BI", "Tableau", "Looker", "Excel"},
    {"Pandas", "NumPy", "Spark", "Data Analysis", "Statistics"},
    {"Airflow", "dbt", "ETL", "Spark"},
    {"Machine Learning", "Deep Learning", "NLP", "LLMs", "PyTorch", "TensorFlow", "scikit-learn"},
    {"Java", "Kotlin", "Scala"},
    {"Android", "iOS", "React Native", "Flutter", "Swift", "Kotlin"},
    {"REST APIs", "GraphQL", "gRPC", "Microservices"},
    {"REST APIs", "FastAPI", "Django", "Flask", "Express", "Spring", "Node.js"},
    {"Unit Testing", "Selenium"},
]

_ALIAS_TO_CANONICAL = {a: c for c, aliases in VOCABULARY.items() for a in [c.lower(), *aliases]}
# Names that are also ordinary words or letters: they must appear with this exact
# capitalization and next to other technical terms ("Python, R, and SQL", not "Excel at").
_CASE_SENSITIVE = {"r": "R", "go": "Go", "rust": "Rust", "swift": "Swift", "excel": "Excel",
                   "express": "Express", "spring": "Spring", "node": "Node", "ts": "TS", "js": "JS",
                   "ml": "ML", "rest": "REST", "git": "Git", "agile": "Agile"}  # fmt: skip


def _pattern(alias: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9+#./-]){re.escape(alias)}(?![A-Za-z0-9+#-])", flags)


_PATTERNS = {
    alias: _pattern(_CASE_SENSITIVE[alias]) if alias in _CASE_SENSITIVE else _pattern(alias, re.I)
    for alias in _ALIAS_TO_CANONICAL
}


def canonical(name: str) -> str:
    """Canonical skill name, or the cleaned input if it's not in the vocabulary."""
    key = " ".join(name.lower().split())
    return _ALIAS_TO_CANONICAL.get(key, " ".join(name.split()))


def _technical_neighbour(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 50) : end + 50]
    return any(
        p.search(window)
        for alias, p in _PATTERNS.items()
        if alias not in _CASE_SENSITIVE and len(alias) > 3
    )


def find_skills(text: str, extra: list[str] | None = None) -> list[str]:
    """Skills mentioned in a text, in order of first mention.

    `extra` (the profile's own skills) catches niche skills outside the vocabulary.
    """
    hits: dict[str, int] = {}
    for alias, canon in _ALIAS_TO_CANONICAL.items():
        m = _PATTERNS[alias].search(text)
        if not m:
            continue
        if alias in _CASE_SENSITIVE:
            following = text[m.end() : m.end() + 4].lower()
            if following.startswith((" at ", " in ")) or not _technical_neighbour(text, *m.span()):
                continue
        hits[canon] = min(hits.get(canon, m.start()), m.start())
    for skill in extra or []:
        canon = canonical(skill)
        if canon in hits or len(canon) < 3:
            continue
        m = _pattern(canon, re.I).search(text)
        if m:
            hits[canon] = m.start()
    return [s for s, _ in sorted(hits.items(), key=lambda kv: kv[1])]


def related_to(skill: str) -> set[str]:
    return set().union(*(g for g in RELATED_GROUPS if skill in g)) - {skill}


@dataclass
class SkillMatch:
    name: str
    status: SkillStatus
    # Verified profile skills behind the status, e.g. ["FastAPI"] for a related "Django".
    profile_skills: list[str] = field(default_factory=list)


def classify(job_skills: list[str], profile_skills: dict[str, str]) -> list[SkillMatch]:
    """`profile_skills` maps canonical skill -> how it appears in the verified profile."""
    result: list[SkillMatch] = []
    for skill in job_skills:
        if skill in profile_skills:
            result.append(SkillMatch(skill, "demonstrated", [profile_skills[skill]]))
            continue
        related = sorted(profile_skills[s] for s in related_to(skill) if s in profile_skills)
        result.append(SkillMatch(skill, "related" if related else "not_demonstrated", related))
    return result


_POINTS = {"demonstrated": 1.0, "related": 0.5, "not_demonstrated": 0.0}


def skills_score(matches: list[SkillMatch]) -> int | None:
    if not matches:
        return None
    points = sum(_POINTS[m.status] for m in matches)
    return round(100 * points / len(matches))
