# Job Intelligence & Personal Job CRM

A personal job-search assistant: resume in, ranked jobs out, then a job CRM, resume tailoring
and cover letters. It is **not** an auto-apply bot. See [AGENTS.md](AGENTS.md) for scope and rules,
and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it fits together.

Status: **Phase 8 (More job sources)**. Search Greenhouse, Lever and Ashby company boards and
the Remote OK, We Work Remotely, Remotive, Himalayas and Jobspresso remote feeds (Adzuna with
your own keys), import job alert emails (LinkedIn, Naukri, Indeed) and WhatsApp job messages in bulk, and import
any job page that publishes standard job data (including Workday,
SmartRecruiters, iCIMS, Taleo and SuccessFactors pages). LinkedIn, Naukri and similar sites are
never fetched: paste their descriptions. Draft cover letters where every sentence about you cites your
resume and every sentence about the company quotes the posting. Tailor your resume for a job: every change is checked
against your verified resume and needs your approval, then download it as PDF or DOCX in the same layout as the resume you uploaded. Track applications on a Kanban board with notes, interviews and
history, and see which sources and match levels lead to interviews. Jobs are scored 0–100 with a
breakdown and ranked. Upload a resume and get a verified, versioned profile. Set
preferences, add company Greenhouse boards and search them, then review normalized,
de-duplicated jobs with eligibility reasons. You can also import any job by link or pasted
description. With AI processing on, the best jobs also get an AI review (Gemini). All planned
phases are built. See [docs/AI.md](docs/AI.md) and
[docs/CONNECTORS.md](docs/CONNECTORS.md).

## Prerequisites

- Docker with Docker Compose v2
- For running outside Docker and for `make check`: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22, GNU Make

## Quick start (everything in Docker)

```bash
make dev
```

This creates `.env` from `.env.example` (with a generated `JWT_SECRET`) on first run, then builds
and starts five services:

| Service | URL |
|---|---|
| web (Next.js) | http://localhost:3000 |
| api (FastAPI) | http://localhost:8000 (docs at http://localhost:8000/api/docs) |
| db (Postgres 16 + pgvector) | localhost:5433 |
| redis | localhost:6379 |
| worker | Background resume parsing (RQ). No port |

The API container applies migrations on start. Open http://localhost:3000, choose **Create one**,
and register. Stop with `Ctrl+C`, or `make down` if started detached.

Without Make: `cp .env.example .env`, set `JWT_SECRET`, then `docker compose up --build`.

## Environment variables

All configuration comes from `.env` at the repo root. `.env.example` lists every variable.

| Variable | Used by | Purpose |
|---|---|---|
| `DATABASE_URL` | api | Postgres URL. In Docker the API uses `db:5432` automatically |
| `TEST_DATABASE_URL` | tests | Test database. **Wiped by the tests**; must end in `_test` |
| `POSTGRES_HOST_PORT` | compose | Host port for Postgres (default 5433, avoids clashing with a local Postgres) |
| `REDIS_URL` | api | Redis URL (rate limiting now, job queue later) |
| `JWT_SECRET` | api | Signs session tokens. At least 32 characters. `make` generates one |
| `ACCESS_TOKEN_TTL_MINUTES` | api | Session length (default 1440 = 1 day) |
| `COOKIE_SECURE` | api | `true` when served over HTTPS |
| `ALLOW_REGISTRATION` | api | Set `false` once your account exists |
| `AUTH_RATE_LIMIT`, `AUTH_RATE_WINDOW_SECONDS` | api | Login/register attempts allowed per IP per window |
| `CORS_ORIGINS` | api | Comma-separated web origins allowed to call the API |
| `NEXT_PUBLIC_API_URL` | web | API base URL as seen by the browser |
| `STORAGE_PATH` | api, worker | Where uploaded resumes are stored |
| `MAX_UPLOAD_BYTES`, `MAX_RESUME_PAGES`, `PARSE_JOB_TIMEOUT_SECONDS` | api, worker | Upload limits and the parse job's hard timeout |
| `AI_PROVIDER` | api, worker | `gemini` (default), `openai` or `none` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | worker | Gemini key and model. Without a key, resumes use the built-in basic parser |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | worker | OpenAI key and model (when `AI_PROVIDER=openai`) |
| `LLM_TIMEOUT_SECONDS`, `LLM_MONTHLY_TOKEN_BUDGET` | worker | Per-call timeout; hard monthly token cap per user |
| `AI_RATE_LIMIT`, `AI_RATE_WINDOW_SECONDS` | api | Resume uploads/re-parses allowed per user per window |
| `CONNECTOR_USER_AGENT`, `CONNECTOR_TIMEOUT_SECONDS`, `CONNECTOR_REQUEST_DELAY_SECONDS` | worker, api | How job sources are called |
| `MAX_GREENHOUSE_BOARDS` | api, worker | Board limit per user |
| `ENABLE_MOCK_CONNECTORS` | worker | Fictional LinkedIn/Naukri/Indeed jobs for development (labeled as mock) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | api, worker | Optional Adzuna API keys (register at developer.adzuna.com and accept their terms) |
| `REMOTIVE_MIN_INTERVAL_SECONDS`, `REMOTEOK_MIN_INTERVAL_SECONDS`, `WEWORKREMOTELY_MIN_INTERVAL_SECONDS`, `JOBSPRESSO_MIN_INTERVAL_SECONDS`, `HIMALAYAS_MIN_INTERVAL_SECONDS` | worker | Minimum time between fetches of the remote feeds (defaults 6h, 1h, 1h, 1h, 6h) |
| `SEARCH_RATE_LIMIT`, `SEARCH_RATE_WINDOW_SECONDS` | api | Searches, imports and board additions per user per window |
| `GEMINI_EMBEDDING_MODEL`, `OPENAI_EMBEDDING_MODEL` | worker | Embedding models (768 dims) |
| `EMBEDDING_MAX_JOBS_PER_RUN` | worker | Jobs embedded per scoring run, eligible ones first |
| `ENVIRONMENT`, `LOG_LEVEL` | api | `development` / `test` / `production`; log level |

## Running locally without Docker (hot reload)

```bash
make setup     # uv sync + npm ci, creates .env
make api       # starts db + redis in Docker, migrates, runs the API on :8000 with reload
make worker    # in another terminal: resume-parsing worker
make web       # in another terminal: Next.js dev server on :3000
```

AI parsing only runs when a key is configured **and** you turn on "AI processing" in Settings.

To find jobs: open **Jobs → Sources**, add a company's Greenhouse board token (for example
`gitlab`), set your **Preferences**, then press **Search** on the Jobs page.
Otherwise the basic parser is used and the resume page says so.

## Migrations

Alembic config is in `apps/api/alembic.ini`; migration scripts live in
`infrastructure/migrations/`.

```bash
make migrate        # alembic upgrade head
make migrate-down   # alembic downgrade base
```

Equivalent raw commands: `cd apps/api && uv run alembic upgrade head` (or `downgrade base`).
Inside Docker: `docker compose exec api alembic upgrade head`.

New migration: `cd apps/api && uv run alembic revision --autogenerate -m "describe change"`.
Review the result before committing.

## Tests and checks

```bash
make check
```

Starts db + redis if needed, then runs:

- API: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (uses `jobcrm_test`)
- Web: ESLint, Prettier check, `tsc` (strict), Vitest
- A check that `apps/web/types/api.ts` matches the current OpenAPI schema

Individual parts: `make check-api`, `make check-web`, `make check-types`. CI
(`.github/workflows/ci.yml`) runs `make setup && make check`.

Tests never call a real LLM or external service.

## Generated API types

`apps/web/types/api.ts` is generated from FastAPI's OpenAPI schema. **Do not edit it by hand.**
After changing an API route or schema:

```bash
make types
```

`make check` fails if the file is stale or edited.

## Deploying (free)

Vercel (website), Render (API and worker in one free container), Neon (Postgres + pgvector) and
Upstash (Redis). Step-by-step: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The blueprint is
[render.yaml](render.yaml).

## Repository layout

```
apps/api/app        api/ core/ models/ schemas/ services/ repositories/
                    connectors/ ai/ workers/ utils/   (FastAPI backend)
apps/api/tests      pytest suite
apps/web            Next.js app (app router, Tailwind, shadcn/ui, TanStack Query)
infrastructure      docker/ (Dockerfiles, Postgres init), migrations/ (Alembic)
docs                ARCHITECTURE, SECURITY, SOURCE_FEASIBILITY, phases/
```

## Troubleshooting

- **Port 5433/6379/8000/3000 already in use**: stop the other process, or change
  `POSTGRES_HOST_PORT` (and the port in `DATABASE_URL`/`TEST_DATABASE_URL`).
- **"Cannot reach the API" in the browser**: check `curl localhost:8000/api/health` and that
  `CORS_ORIGINS` includes the web origin.
- **Reset all local data**: `make clean` (deletes the Docker volumes).
# job_intelligence
