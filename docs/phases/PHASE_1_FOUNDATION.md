# Phase 1 — Foundation

Read `AGENTS.md` first and follow it. This phase builds the skeleton only. No resume parsing, job search, matching or AI calls yet.

## Step 0: inspect before writing code

Before creating anything, report:

1. What already exists in the repository (files, tooling, versions)
2. Your proposed folder structure for this phase
3. The database schema for the tables this phase needs
4. Any conflict between this prompt and what exists
5. Risks or open questions

Wait for my approval if anything conflicts with `AGENTS.md`. Otherwise continue.

## Deliverables

### Monorepo

- `apps/web` (Next.js, TypeScript strict, Tailwind, shadcn/ui, TanStack Query)
- `apps/api` (FastAPI, Pydantic, SQLAlchemy, Alembic)
- `infrastructure/docker`, `docker-compose.yml` running: web, api, postgres (with pgvector enabled), redis
- `.env.example` with `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `NEXT_PUBLIC_API_URL`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `STORAGE_PATH`
- Lint and format config for both apps (ruff + mypy for Python, ESLint + tsc for web)
- A single command to run everything (for example `make dev`) and a single command to run all checks (`make check`)

### Backend foundation

- App factory, config via environment (Pydantic settings), structured JSON logging
- `GET /api/health` (checks DB connectivity)
- Auth: register, login, logout, `GET /api/me`. Password hashing with argon2 or bcrypt. JWT in an httpOnly SameSite=Lax cookie. CSRF token on mutating requests
- Rate limiting on auth endpoints
- Alembic set up, with an initial migration creating: `users`, `candidate_profiles` (empty shell, `user_id` FK, versioned), `settings`
- pgvector extension enabled in the first migration
- Repository + service pattern demonstrated once end to end (users)
- OpenAPI export script that generates TypeScript types into `apps/web/types/api.ts`

### Frontend foundation

- App shell: sidebar navigation, top bar, responsive layout, light theme (dark optional)
- Pages: `/login`, `/dashboard` (placeholder cards), `/settings`; routes for the other pages exist as "coming in a later phase" stubs
- Auth flow: login, logout, protected routes, redirect when unauthenticated
- API client using the generated types and TanStack Query
- Dashboard placeholder shows the planned sections (pipeline counts, high-match jobs, resume insights) with empty states, not fake data

### Tests

- Backend: auth (register, login, wrong password, protected route, CSRF rejection), health, a migration up/down test
- Frontend: login form validation, protected route redirect
- CI config (GitHub Actions) running `make check`

### Docs

- `README.md` with setup, env vars, running web/api/db, running migrations, running tests
- `docs/ARCHITECTURE.md` (short; reflects decisions in `AGENTS.md`)
- `docs/SECURITY.md` (auth model, CSRF, rate limits, secret handling)

## Out of scope for this phase

Resume upload, parsing, AI providers, connectors, job tables, matching, CRM, workers beyond a Redis connection check.

## Definition of Done

Run each of these and show me the output:

- [ ] `docker compose up` starts all services cleanly from a fresh clone
- [ ] `alembic upgrade head` and `alembic downgrade base` both succeed
- [ ] `make check` passes: ruff, mypy, pytest, ESLint, tsc, frontend tests
- [ ] I can register, log in, see the dashboard, log out, and am redirected when logged out
- [ ] `GET /api/health` reports the DB as healthy
- [ ] Generated TS types are produced by a script and are not hand-edited
- [ ] No secrets in the repo; `.env.example` is complete
- [ ] README instructions work exactly as written (verify by following them)

Finish with: what was built, what was tested, anything deferred, and the proposed plan for Phase 2.
