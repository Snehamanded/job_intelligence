# Phase 2 — Resume intelligence

Read `AGENTS.md` first. Written from the plan proposed at the end of Phase 1, plus the owner's
answers:

- Default LLM provider: Gemini. OpenAI is the alternative.
- It must work with or without real API keys.
- Test resumes are fictional and written for the tests.
- Data export and delete are in scope.

## Goal

Upload a resume and get a **verified** structured profile: every extracted item points at the
resume text it came from, and items that can't be verified are shown but excluded. The user
reviews the profile, corrects it and sets job preferences. Each change creates a new profile
version.

## Deliverables

### Upload and storage
- `POST /api/resumes` (multipart). PDF, DOCX and TXT only.
  - The type is detected from magic bytes, and the extension must agree with it.
  - Limits on size (`MAX_UPLOAD_BYTES`), PDF pages (`MAX_RESUME_PAGES`), extracted characters,
    and DOCX uncompressed size (protects against zip bombs).
- Files are stored under `STORAGE_PATH/<user_id>/` with server-generated names. The original
  filename is metadata only.
- List, get, delete and download for the user's own resumes. Another user's resume returns `404`.

### Parsing (RQ worker)
- Upload enqueues a parse job with a hard timeout. A `worker` service is added to docker compose.
- Steps:
  1. Extract the text.
  2. Run the deterministic heuristic parser. It always runs, and it is the fallback.
  3. Run LLM extraction, only when consent is on, a provider is configured and the budget allows.
  4. Validate the evidence.
  5. Create a new profile version.
- Status moves `queued → parsing → parsed | failed`. A failure stores a clear message for the
  user and never a stack trace.
- If the same text was already parsed with the same prompt and model, the earlier extraction is
  reused, so the LLM is not called again.

### AI layer
- `AIProvider` interface with `GeminiProvider` (default), `OpenAIProvider` and `FakeAIProvider`.
  SDK calls happen only in `ai/providers/`.
- Prompts live in `ai/prompts/resume_extraction.py`. Resume text goes in as delimited, escaped
  data, never as instructions.
- Output is validated against a Pydantic schema. One retry on invalid output, then fall back to
  the heuristic parser.
- Every call is recorded in `llm_usage`. A monthly per-user token budget (`LLM_MONTHLY_TOKEN_BUDGET`)
  is a hard cap that is checked before each call.
- Upload and reparse are rate-limited per user.

### Truthfulness
- Every extracted item carries `evidence` (a verbatim quote) and a `source_span` (character
  offsets into the extracted text) that the code computes. The LLM cannot supply spans.
- Items whose evidence isn't found in the text are marked `UNSUPPORTED`, shown to the user and
  excluded from the saved profile.
- Experience dates are parsed in code from the quoted date text. Total experience months are
  computed in code, with overlapping roles merged.
- Items the user adds by hand are labeled `source: user`.

### Profile and preferences
- `candidate_profiles` gains: `resume_id`, `origin` (`parsed` | `edited`), `parse_method`
  (`llm` | `heuristic`), `data` (JSONB), `experience_months` and the explicit preference fields
  from AGENTS.md §6.
  - The preference fields are `target_roles`, `remote_scope`, `onsite_locations`, `open_to`,
    `min_salary`, `currency` and `salary_unknown_policy`.
- `GET /api/profile`, `GET /api/profile/versions`, `PUT /api/profile`. Each edit makes a new
  version and keeps the preferences.
- Onsite locations are normalized, for example "Bangalore" becomes "Bengaluru".

### Privacy
- `GET /api/me/export` returns all of the user's data as JSON.
- `DELETE /api/me` requires the password, deletes the user's rows and stored files, and clears
  the session.

### Frontend
- `/resume`: upload, status with polling, and profile review.
  - Review shows each item's evidence, removed items, the "excluded as unsupported" list and
    how it was parsed (AI or basic).
- `/preferences`: the preferences form.
- Dashboard "Resume insights" shows real data when a profile exists.
- Settings: export and delete account.

## Out of scope
Job search, embeddings, matching, OCR for scanned PDFs, tailoring.

## Definition of Done
- [ ] `make check` passes (ruff, mypy, pytest, ESLint, tsc, Vitest, types up to date)
- [ ] Migrations upgrade and downgrade cleanly
- [ ] Unit tests: file validation, text extraction, experience/date parsing, evidence
      validation, heuristic parsing, location normalization, prompt construction
- [ ] Integration tests: upload → parse → profile, LLM path (fake provider), consent off,
      budget exceeded, invalid LLM output fallback, per-user isolation, preferences versioning,
      export, account delete
- [ ] No test calls a real LLM
- [ ] Running in Docker: upload a PDF, DOCX and TXT, and see a parsed profile, preferences saved
      and export/delete working
- [ ] Docs updated (README, ARCHITECTURE, SECURITY, `docs/AI.md`)
