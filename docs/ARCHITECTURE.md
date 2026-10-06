# Architecture

Short reference. The decisions themselves live in [AGENTS.md](../AGENTS.md) §4. This file
describes how they are realised in the code.

## Shape

Modular monolith: one FastAPI app, one Next.js app, Postgres (with pgvector) and Redis. No
microservices, separate vector DB or agent framework.

```
browser ── Next.js (apps/web, :3000)
   │  fetch, credentials: include, X-CSRF-Token
   ▼
FastAPI (apps/api, :8000) ── Postgres + pgvector (:5432 in Docker, :5433 on host)
        │                 └─ Redis (rate limits, RQ queue)
        └─ enqueue ──► worker (RQ, same image) ── Gemini / OpenAI (only with consent)
                         │
              shared upload volume (STORAGE_PATH)
```

## Backend (`apps/api/app`)

| Package | Responsibility |
|---|---|
| `api/` | Routers and request dependencies only (auth, CSRF, rate limit). No business logic |
| `services/` | Business logic. Owns transactions (`commit`) |
| `repositories/` | Data access. Every query on a user-owned table filters on `user_id` |
| `models/` | SQLAlchemy 2.0 models (`Mapped[...]`), shared naming convention for constraints |
| `schemas/` | Pydantic request/response models. Also the source of the OpenAPI schema |
| `core/` | Settings (pydantic-settings), DB engine, Redis, security, rate limiter, JSON logging |
| `services/resume/` | Upload validation and text extraction (`documents.py`), heuristic parser, evidence validator, parsing pipeline |
| `ai/` | Prompts, providers (the only SDK imports), AI services. See [AI.md](AI.md) |
| `workers/` | RQ queue (`TaskQueue` protocol, so tests run jobs inline), tasks and the worker entry point |
| `utils/` | Pure helpers: text normalization and quote search, date ranges, location names |
| `connectors/` | Job sources behind one interface (Greenhouse, mocks). See [CONNECTORS.md](CONNECTORS.md) |
| `services/jobs/` | Normalization, dedupe (`JobStore`), eligibility, search runs, manual import, listing |
| `services/crm.py` | Applications, stage rules and history, notes, interviews, analytics |
| `services/cover_letters/` | Sentence checks (claim, company, connective), template letter, AI draft and verification, DOCX |
| `services/tailoring/` | Tailored document model, rule-based changes, truthfulness checks, AI suggestion and verification, PDF and DOCX downloads in the uploaded resume's layout |
| `services/matching/` | Skill vocabulary and status, score components, scoring config versions, LLM refinement, `MatchingService` |

Request flow (users example): `api/routes/auth.py` → `services/auth.py` (`AuthService`) →
`repositories/users.py` (`UserRepository`) → `models/user.py`.

`create_app()` in `app/main.py` is the app factory. `app/asgi.py` is the uvicorn entry point.
The DB layer is synchronous SQLAlchemy with psycopg 3. FastAPI runs sync routes in a threadpool,
which is enough for a single-user app and keeps the code simple.

### Data model

| Table | Notes |
|---|---|
| `users` | UUID PK, email stored lowercased and unique, argon2 `password_hash`, `is_active` |
| `settings` | One row per user: `llm_consent`, `llm_consent_at` |
| `resumes` | Uploaded file metadata (`storage_key` is server-generated), `status` (`queued`/`parsing`/`parsed`/`failed`), user-facing `error_message`/`parse_notice`, `extracted_text` (the text spans point into) |
| `candidate_profiles` | **Immutable versions**, unique `(user_id, version)`, one `is_current`. `data` JSONB (`ProfileData`: items with `evidence` + `source_span`, plus `unsupported` claims), `experience_months` computed in code, `origin` (`parsed`/`edited`), `parse_method` (`llm`/`heuristic`), and the explicit preference columns from AGENTS.md §6 |
| `llm_usage` | One row per LLM call attempt (tokens, success). Used for the monthly budget |
| `ai_extractions` | Validated LLM output cached per user by `(task, content_hash, prompt_version, model)` |
| `jobs` | Normalized postings per user, unique `(user_id, source, source_job_id)`. Locations/cities/countries/remote regions, salary (min/max/currency/period/verbatim text, `salary_unknown`), experience, plain-text description, `dedupe_key`, `content_hash`, `also_seen_on` |
| `search_runs` | Status, keywords and `source_results` (one entry per connector) |
| `job_source_configs` | The user's Greenhouse board tokens |
| `embeddings` | pgvector `vector(768)` per user, unique `(user_id, content_hash, model)` |
| `scoring_configs` | Versioned weights, ranking, bands and top-N per user; one `is_current` |
| `applications` | One per job per user (partial unique index), with a snapshot of title, company, location, URL, source and the match at save time, so it outlives the job (`job_id` `SET NULL`). Stage, `applied_at`, `closed_at`, next action, board position |
| `application_events` | History: created, stage changed (from → to), interview added, interview outcome |
| `application_notes`, `interviews` | Notes; interviews with kind, time (timezone-aware), place or link, outcome and a `[{text, done}]` checklist |
| `cover_letters` | Per-user versions: tone, length, optional base tailored version, `paragraphs` (tagged sentences with sources or quotes, checks, include flags, author label), `content` (frozen on save) |
| `resume_versions` | A tailored resume per job: per-user version number, the profile version it's based on, `changes` (with labels, checks and decisions), `content` (the approved document, immutable once `saved`) |
| `job_matches` | Score per `(job, profile_version, scoring_config_version)`: match, rank, label, eligibility, high priority, component breakdown, skill statuses, explanation and its source |

Every change to the profile (re-parse, edit, preferences) inserts a new version, so Phase 4
match rows keyed by `profile_version` are invalidated automatically.

All user-owned tables have `user_id` with `ON DELETE CASCADE`, so deleting a user deletes their
data. The first migration enables the `vector` extension.

Migrations live in `infrastructure/migrations/` (Alembic). `tests/test_migrations.py` runs
down/up and checks that the models match the migrations (autogenerate diff is empty).

## Frontend (`apps/web`)

- Next.js app router, TypeScript strict, Tailwind v4, shadcn/ui components in `components/ui/`.
- `app/(app)/` is the authenticated area. Its layout wraps pages in `AuthGuard` and `AppShell`
  (sidebar + top bar, mobile drawer).
- `lib/api/client.ts` is an `openapi-fetch` client typed by `types/api.ts`. Hooks in
  `lib/api/*.ts` wrap it with TanStack Query.
- `types/api.ts` is generated (`make types`) from the API's OpenAPI schema. Never hand-edited.
  `make check` enforces this.

## CRM rules

- **Stages:** the user moves applications freely between `saved`, `applied`, `interviewing`,
  `offer`, `rejected` and `withdrawn`, and every move is recorded.
- **Dates:** `applied_at` is set the first time an application reaches applied or later.
  `closed_at` is set on rejected or withdrawn and cleared on reopening.
- **Interviews:** adding one to a saved or applied application moves it to interviewing.
- **Analytics** (`GET /api/analytics`) uses the furthest stage each application ever reached, from
  its history:
  - Applied: has `applied_at`, or reached applied.
  - Responded: reached interviewing, or was rejected after applying.
  - Rates are out of applications actually sent. They are broken down by source and by the match
    label at save time.
- **No submission:** nothing in the CRM submits anything. The user applies on the employer's site.

## Configuration

Everything is configured through environment variables (`.env`, see `.env.example`). Nothing
user-specific is hard-coded.

## Logging

The API logs one JSON object per line to stdout. Every request emits `request_completed`
(method, path, status, duration). Domain events (`user_registered`, `login_succeeded`,
`login_failed`, …) are logged by services. A denylist redacts sensitive keys.
