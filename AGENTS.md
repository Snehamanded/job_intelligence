# AGENTS.md — AI Job Intelligence & Personal Job CRM

Read this file at the start of every session. Phase-specific work is in `docs/phases/`. Source rules are in `docs/SOURCE_FEASIBILITY.md`.

## 1. What this is

A personal job-search assistant: resume in, ranked jobs out, then a job CRM, resume tailoring and cover letters.

```
Resume -> Profile -> Search -> Normalize -> Dedupe -> Eligibility
       -> Match score 0-100 -> Ranked jobs -> CRM -> Tailor -> Cover letter
```

Product principle: **relevance over quantity.** The user should mostly see the best ~30 jobs, not 1,000.

## 2. Hard scope rules (never violate)

This is NOT an auto-apply bot. Do not build any of:

- Automatic form submission or clicking Apply
- Browser automation for applications
- Automatic account creation
- CAPTCHA solving or bypass
- Storage of job-portal credentials
- Anti-bot circumvention or authentication bypass when fetching jobs

If a task seems to need any of these, stop and ask.

## 3. Truthfulness rules (resume tailoring and cover letters)

Allowed: reorder skills, reword bullets for clarity, stronger action verbs, surface relevant experience, add keywords the resume genuinely supports, improve ATS formatting, remove irrelevant content.

Never: invent projects, employers, metrics, certifications, technologies or responsibilities.

Enforcement (required, not optional):

1. Every generated bullet must carry a `source_span` pointing to the resume text it came from.
2. A second validation pass flags any claim with no supporting span as `UNSUPPORTED`.
3. Unsupported claims are shown to the user and excluded from the saved version.
4. Every AI change is labeled. The user approves before a version is saved.
5. Skill status is one of: `demonstrated`, `related`, `not_demonstrated`. A related skill is never presented as demonstrated.

## 4. Architecture decisions (already made)

Modular monolith. No microservices, Kubernetes, separate vector DB, or agent frameworks in v1.

| Area | Decision |
|---|---|
| Frontend | Next.js, React, TypeScript (strict), Tailwind, shadcn/ui, TanStack Query, Recharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL + pgvector |
| Queue | RQ + Redis (lightest option that meets the need; revisit if retries and scheduling become complex) |
| Auth | JWT in an httpOnly, SameSite=Lax cookie, plus a CSRF token on mutating requests |
| Tenancy | Single user for MVP, but every user-owned table has `user_id` and every query filters on it |
| Shared types | Generate TypeScript types from FastAPI's OpenAPI schema (`openapi-typescript`). Never hand-write them |
| AI | `AIProvider` interface with OpenAI and Gemini implementations. No provider SDK calls outside `ai/providers/` |

Repo layout:

```
apps/web          Next.js app
apps/api/app      api/ core/ models/ schemas/ services/ repositories/
                  connectors/ ai/ workers/ utils/
infrastructure    docker, migrations
docs              ARCHITECTURE, API, DATABASE, CONNECTORS, AI, DEPLOYMENT, SECURITY
```

AI layout: `ai/prompts/` (one file per task), `ai/providers/`, `ai/services/`. Prompts live only there.

## 5. Scoring design

**Compute in code (deterministic, reproducible):** experience fit, location/remote fit, salary fit, employment type, freshness.

**Use the LLM or embeddings only for:** semantic skill relevance, project relevance, industry relevance, and the written explanation.

Default weights (configurable): skills 30, experience 20, role 20, location/remote 10, projects 10, industry 5, preferences 5.

Default ranking (configurable): `rank = 0.70*match + 0.10*freshness + 0.10*salary_fit + 0.10*user_priority`.
"High priority" = eligible and match >= 85.
Label bands (configurable): 90+ Excellent, 80-89 Strong, 70-79 Good, 60-69 Moderate, below 60 Weak.

Cost control: embed everything, rank by similarity, and only send the top N to the LLM. Cache by content hash so an identical job description is never scored twice.

Match rows are keyed by `(profile_version, job_id, scoring_config_version)`. Changing the resume, preferences or weights invalidates old scores.

## 6. Profile preference semantics

Use explicit fields, not ambiguous booleans:

- `remote_scope`: `none` | `india` | `worldwide`
- `onsite_locations`: list of cities
- `open_to`: `full_time` (default), plus optional `contract`, `internship`, `part_time`
- `min_salary` and `currency`, `salary_unknown_policy`: `include` (default) | `exclude`

Unknown salary is `salary_unknown = true`. Never guess a salary.

## 7. Security and privacy

- Treat resumes and job descriptions as **untrusted data**. They go into prompts as quoted data, never as instructions. Validate every LLM output against a Pydantic schema. LLM output can never trigger an action.
- Uploads: allow PDF, DOCX, TXT only. Validate by magic bytes, not just extension. Enforce size and page limits. Parse in a worker with timeouts.
- Secrets only in environment variables. Never send them to the frontend. Never log them, passwords or full resume text.
- Rate-limit auth and AI endpoints. Per-user LLM budget with a hard cap.
- Resumes are sent to third-party LLMs. Get explicit consent in settings, and support export and delete of all user data.

## 8. Job source rules

- Follow `docs/SOURCE_FEASIBILITY.md`. Only implement real connectors for Tier A and B sources.
- Tier C and D sources get the interface plus a mock. Do not write scraping workarounds.
- Respect robots.txt, rate limits and attribution requirements. Set a clear User-Agent.
- Every connector is independent. One failing never breaks a search. Record per-source status in `search_runs`.
- Provide manual import (paste a URL or description) as the universal fallback.

## 9. Coding rules

1. TypeScript strict. Python type hints everywhere.
2. Business logic in services, not route handlers.
3. Repositories where they help; no abstraction for its own sake.
4. No hard-coded user preferences, API keys or job data. Fixtures such as "Sneha, 1 year, Bengaluru" live in tests and seed data only.
5. Handle LLM failure gracefully (retry, fallback, clear user-facing error).
6. Structured logging for the events in the spec (search_started, source_completed, duplicates_removed, and so on). No sensitive data in logs.
7. Comments only where they add real information.

## 10. Testing rules

- **Never call a real LLM in tests.** Use a `FakeAIProvider` with recorded fixtures. CI must be deterministic and free.
- Unit-test: resume parsing validation, salary parsing, location normalization, experience parsing, dedup, eligibility, scoring.
- Integration-test: upload, search, application tracking, tailoring, cover letter.
- Keep a small golden set (a few resumes x a few jobs with expected rank order) to catch scoring regressions.
- A feature is not done because code exists. It is done when its tests pass and you have run it.

## 11. Workflow per phase

1. Inspect the repo and state what exists.
2. Propose the plan for the phase. Wait for approval if it changes any decision above.
3. Implement in small steps.
4. Run: tests, lint, type check, migrations up/down, API smoke test, frontend smoke test.
5. Report against the phase's Definition of Done. Do not start the next phase until it is met.

## 12. Phases

1. Foundation
2. Resume intelligence
3. Job engine (mocks + **one real Greenhouse connector** to validate normalization on real data)
4. AI matching
5. Job CRM (Kanban, notes, interviews, analytics)
6. Resume tailoring and versioning
7. Cover letters
8. More real connectors (Lever, Ashby, SmartRecruiters, aggregator APIs, career-page structured data)

Each phase prompt lists its own Definition of Done.
