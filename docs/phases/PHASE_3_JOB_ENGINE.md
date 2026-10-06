# Phase 3 — Job engine

Read `AGENTS.md` first. Written from the plan proposed at the end of Phase 2, which the owner
approved. Source rules are in `docs/SOURCE_FEASIBILITY.md`.

## Goal

Fetch jobs from real and mock sources and normalize them into one shape. Remove duplicates and
mark each job eligible or not against the user's preferences, all in deterministic code with no
LLM. Matching scores come in Phase 4.

## Greenhouse verification (2026-10-05)

- Docs (`docs.greenhouse.io/job-board.html`): `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`,
  `.../jobs/{id}?pay_transparency=true` and `.../boards/{token}`. GET needs no authentication.
  No published rate limits.
- `boards-api.greenhouse.io/robots.txt` disallows only `/embed/`.
- Real payloads checked on 2026-10-05 (GitLab, Airbnb, Groww):
  - Pay usually appears in the description ("Salary Range $X — $Y USD"), and `pay_input_ranges`
    is often empty.
  - Locations are free text ("Bengaluru-VTP, India", "Remote, Canada; Remote, US").

## Deliverables

### Data
- `jobs` (user-owned): source, source job id, URL, title, company, normalized locations,
  `remote_type` (`remote`/`hybrid`/`onsite`/`unknown`), `remote_regions`, employment type, salary
  (min/max/currency/period plus verbatim text, `salary_unknown`), experience min/max years,
  description as plain text, content hash, posted/first-seen/last-seen times, raw payload,
  dedupe key, and the other sources the same job was seen on.
- `search_runs`: status, keywords, per-source results (status, fetched, kept, new, duplicates,
  error, duration), timestamps.
- `job_source_configs`: the user's Greenhouse board tokens (validated against the board API).

### Connectors
- A `JobConnector` interface returns normalized `JobPosting`s. Every connector is independent:
  one failing never breaks a search.
- **Greenhouse** (Tier A, real): per board token, with a clear User-Agent, timeouts, a polite
  delay between requests and a cap on the number of boards.
- **Mocks** for Tier C sources (LinkedIn, Naukri, Indeed): same interface, deterministic
  fictional jobs, **off by default** (`ENABLE_MOCK_CONNECTORS`) and always labeled "mock".
- **Manual import**: paste a Greenhouse job URL (fetched through the API), or paste a job
  description with title, company and location.

### Normalization (code only)
- Salary parsing: currency symbols and codes, k/lakh/LPA/crore, ranges, periods, "—" and "to".
  Ambiguous text gives `salary_unknown`. No salary is ever guessed.
- Experience parsing: "3+ years", "1–2 years", "minimum 2 years", "8-12 years".
- Location and remote parsing, including multi-location strings, office suffixes and country names.
- Employment type from the title and text (intern, contract, part-time).
- HTML to plain text (the description is never stored as HTML).

### Search pipeline (worker)
- `POST /api/searches` takes keywords (defaulting to the target roles). The worker runs every
  enabled connector, keeps titles that match the keywords, normalizes, removes duplicates
  (same source id first, then the cross-source key, then the same content hash) and records
  results per source.
- Structured log events: `search_started`, `source_completed`, `source_failed`,
  `duplicates_removed`, `search_completed`.

### Eligibility (code only)
- Checked against the current profile: employment type, location and remote fit, salary floor
  (only when the currency matches; otherwise the salary counts as unknown and
  `salary_unknown_policy` applies), and a large experience gap.
- Each check reports `pass`, `fail` or `unknown` with a reason. Ineligible jobs are hidden by
  default but can be shown.

### API
- `GET/POST/DELETE /api/job-sources`, `GET /api/connectors`
- `POST /api/searches`, `GET /api/searches`, `GET /api/searches/{id}`
- `GET /api/jobs` (filters: eligibility, source, text; sort: newest), `GET /api/jobs/{id}`,
  `DELETE /api/jobs/{id}`, `POST /api/jobs/import`

### Frontend
- `/jobs`: run a search (with keywords), see the last run's per-source status, list jobs (eligible
  by default) with salary or "Salary not listed", experience, remote badge, freshness, source
  and eligibility reasons.
- `/jobs/[id]`: details with the description and a link to the original posting. There is no
  apply automation; the user opens the source.
- `/jobs/sources`: manage Greenhouse boards. `/jobs/import`: manual import.

## Out of scope
Matching scores, embeddings and the LLM (Phase 4). Other real connectors and generic
career-page or JSON-LD URL import (Phase 8). CRM (Phase 5).

## Definition of Done
- [ ] `make check` passes; migrations upgrade and downgrade
- [ ] Unit tests: salary, experience, location/remote, employment type, HTML to text, keyword
      matching, dedupe, eligibility, and Greenhouse normalization on a recorded real payload
- [ ] Integration tests: search with one failing connector (others succeed, status recorded),
      cross-source dedupe, eligibility filtering, manual import (text and Greenhouse URL),
      board validation, per-user isolation
- [ ] No test makes a network call (the HTTP layer is mocked)
- [ ] Running in Docker: add a real Greenhouse board, run a search, and see real normalized jobs
      with eligibility; manual import works
- [ ] `docs/SOURCE_FEASIBILITY.md` Greenhouse row marked verified; `docs/CONNECTORS.md` written
