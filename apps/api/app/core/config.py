from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24

    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    allow_registration: bool = True
    # Comma-separated emails allowed to register (empty: anyone, when registration is allowed).
    # Set this on a public deployment so nobody else can use your AI and API allowances.
    allowed_signup_emails: str = ""

    auth_rate_limit: int = 10
    auth_rate_window_seconds: int = 60

    storage_path: str = "./storage"
    # "database" keeps uploads in Postgres: for hosts without a persistent disk shared with the
    # worker (e.g. Render's free tier).
    storage_backend: Literal["local", "database"] = "local"
    # Run background jobs in the worker process instead of a fork per job (saves memory).
    worker_no_fork: bool = False

    # Resume uploads and parsing
    max_upload_bytes: int = 5 * 1024 * 1024
    max_resume_pages: int = 10
    max_resume_chars: int = 60_000
    max_docx_uncompressed_bytes: int = 20 * 1024 * 1024
    parse_job_timeout_seconds: int = 120

    # AI. Provider SDKs are only used in app/ai/providers/.
    ai_provider: Literal["gemini", "openai", "none"] = "gemini"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    # Fixed so vectors from any provider fit the same pgvector column.
    embedding_dims: int = 768
    # Cosine similarity range mapped to 0-100 (gemini-embedding-2: unrelated text ~0.65).
    # Jobs embedded per scoring run (eligible ones, best first). Keeps within free-tier quotas.
    embedding_max_jobs_per_run: int = 60
    similarity_floor: float = 0.6
    similarity_ceiling: float = 0.9
    llm_timeout_seconds: int = 60
    llm_retry_backoff_seconds: float = 2.0
    llm_monthly_token_budget: int = 2_000_000
    ai_rate_limit: int = 20
    ai_rate_window_seconds: int = 3600

    # Job connectors
    connector_user_agent: str = "JobIntelligence/0.1 (personal job-search assistant)"
    connector_timeout_seconds: int = 20
    connector_request_delay_seconds: float = 1.0
    max_greenhouse_boards: int = 25
    max_jobs_per_source: int = 1000
    enable_mock_connectors: bool = False
    search_job_timeout_seconds: int = 600
    max_job_boards: int = 25
    # Delete jobs not seen for this many days, unless applied to or used for a resume or letter
    # (0 keeps everything). Keeps small free databases from filling up.
    job_retention_days: int = 0
    # A new user's sources are switched on at first use, so the first search needs no setup:
    # every remote feed, Adzuna (India) when configured, and these company boards
    # ("source:identifier:Name", comma-separated; chosen for their India openings, 2026-10-06).
    default_sources_enabled: bool = True
    starter_company_boards: str = (
        "greenhouse:databricks:Databricks,greenhouse:okta:Okta,greenhouse:mongodb:MongoDB,"
        "greenhouse:stripe:Stripe,greenhouse:rubrik:Rubrik,greenhouse:gitlab:GitLab,"
        "greenhouse:razorpaysoftwareprivatelimited:Razorpay,greenhouse:hackerrank:HackerRank,"
        "greenhouse:twilio:Twilio,greenhouse:druva:Druva,greenhouse:groww:Groww,"
        "lever:paytm:Paytm,lever:meesho:Meesho,lever:zeta:Zeta,lever:cred:CRED,"
        "ashby:sarvam:Sarvam AI"
    )
    # Global feeds: minimum time between fetches per user, as the sources ask.
    remotive_min_interval_seconds: int = 6 * 3600  # Remotive: at most ~4 queries a day
    remoteok_min_interval_seconds: int = 3600
    weworkremotely_min_interval_seconds: int = 3600
    jobspresso_min_interval_seconds: int = 3600
    himalayas_min_interval_seconds: int = 6 * 3600  # Himalayas data refreshes daily
    adzuna_app_id: SecretStr | None = None
    adzuna_app_key: SecretStr | None = None
    import_max_bytes: int = 2 * 1024 * 1024
    search_rate_limit: int = 30
    search_rate_window_seconds: int = 3600

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Accept plain postgres URLs (as most tooling writes them) and pin the psycopg 3 driver.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _strong_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator(
        "gemini_api_key", "openai_api_key", "adzuna_app_id", "adzuna_app_key", mode="before"
    )
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _safe_for_production(self) -> "Settings":
        """Refuse to start a public deployment that is missing a protection."""
        if self.environment != "production":
            return self
        problems = []
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (HTTPS)")
        if self.allow_registration and not self.allowed_signup_emails.strip():
            problems.append("set ALLOWED_SIGNUP_EMAILS or ALLOW_REGISTRATION=false")
        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self

    def signup_allowed(self, email: str) -> bool:
        allowed = {e.strip().lower() for e in self.allowed_signup_emails.split(",") if e.strip()}
        return not allowed or email.strip().lower() in allowed

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
