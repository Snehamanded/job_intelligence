# AI

How the app uses LLMs, and the guarantees around them. Read [AGENTS.md](../AGENTS.md) §3 and §7 first.

## Where AI is used (so far)

| Task | Phase | Prompt | Output schema |
|---|---|---|---|
| Resume extraction | 2 | `app/ai/prompts/resume_extraction.py` | `app/ai/schemas.py` → `ResumeExtraction` |
| Job match (skills, projects, industry, explanation) | 4 | `app/ai/prompts/job_match.py` | `JobMatchAssessment` |
| Embeddings (profile and job similarity) | 4 | none | 768-dim vectors in pgvector |
| Resume tailoring suggestions | 6 | `app/ai/prompts/tailor_resume.py` | `TailorSuggestions` |
| Tailoring verification (second pass) | 6 | `app/ai/prompts/tailor_resume.py` | `VerifyReport` |
| Cover letter draft | 7 | `app/ai/prompts/cover_letter.py` | `LetterDraft` |
| Cover letter verification (second pass) | 7 | `app/ai/prompts/cover_letter.py` | `LetterVerifyReport` |
| Finding job posts in pasted alert emails / WhatsApp messages | 8 | `app/ai/prompts/job_posts.py` | `FoundJobPosts` |

Job post finding never writes job text itself: the model quotes each post's first and last words,
the post is sliced from the pasted text in code (`services/jobs/bulk_import.locate`, ignoring
whitespace and chat formatting marks), and title, company, location and link must appear in that
slice or are dropped. Without consent a rule-based split is used.

All AI features from AGENTS.md are now built (Phases 2, 4, 6 and 7).

All LLM calls go through `ai/services/runner.LLMRunner`, which handles consent, the per-user cache,
the hard monthly budget, retry once, Pydantic validation and `llm_usage` records. Embeddings go
through `ai/services/embeddings.EmbeddingService`, with the same budget and its own cache.

## Layout

```
app/ai/
  prompts/      one file per task: system prompt, prompt builder, PROMPT_VERSION
  providers/    AIProvider interface + gemini.py, openai_provider.py, fake.py
                (the only place provider SDKs are imported)
  services/     task orchestration: consent, budget, cache, retry, validation
  schemas.py    Pydantic shapes the LLM must return
```

`get_ai_provider(settings)` returns the configured provider, or `None` when `AI_PROVIDER=none` or no key is set.

| Provider | `AI_PROVIDER` | Default model (override with env) |
|---|---|---|
| Google Gemini (default) | `gemini` | `GEMINI_MODEL=gemini-3.5-flash-lite` |
| OpenAI | `openai` | `OPENAI_MODEL=gpt-6-luna` |

Gemini uses `models.generate_content` with `response_json_schema`. Gemini rejects length/count
keywords (`maxLength`, `maxItems`, …) in a schema this size, so `gemini_schema()` strips them.
Pydantic still enforces them on every response. OpenAI uses the Responses API
with a JSON-schema text format. Both run at temperature 0 (Gemini) or the default (OpenAI), and
neither SDK retries on its own; retries happen in the service.

## Resume pipeline

```
upload ─► validate (magic bytes, size, zip size) ─► store ─► enqueue (RQ, hard timeout)
worker: extract text (pypdf / python-docx / utf-8) ─► normalize
        ├─ consent off / no provider / over budget ─► heuristic parser
        └─ LLM extraction (cached by text hash + prompt version + model)
              invalid output → 1 retry → heuristic parser
        ─► evidence validation ─► new profile version
```

The heuristic parser (`services/resume/heuristic.py`) runs fully locally. It is the fallback
whenever the LLM can't be used, so the app works with no API key at all.

## Matching (Phase 4)

`services/matching/` scores each job 0–100. Weights, ranking and bands are configurable and
versioned in `scoring_configs`.

| Component | Default weight | How |
|---|---|---|
| Skills | 30 | Code: vocabulary + profile skills found in the posting, labeled demonstrated / related / not demonstrated. With no detectable skills it falls back to title fit, capped at 50 |
| Experience | 20 | Code: stated years, or the level implied by the title (Senior ≈ 5, Staff/Lead/Engineering Manager ≈ 8, …) marked "inferred" |
| Role | 20 | Code: title-word overlap with target roles and past titles, blended 60/40 with embedding similarity when available |
| Location | 10 | Code: from the eligibility location check |
| Projects | 10 | AI for the top N (only named, real projects count); code overlap otherwise |
| Industry | 5 | AI for the top N; otherwise neutral (unknown) |
| Preferences | 5 | Code: employment type and salary checks |

- **Ranking:** `rank = 0.70*match + 0.10*freshness + 0.10*salary_fit + 0.10*priority`.
- **High priority:** eligible and match ≥ 85.
- **Versioning:** rows in `job_matches` are keyed by `(job, profile_version, scoring_config_version)`;
  only current rows are shown.

Pipeline, which runs in the worker after a search, a parse, a profile/config/consent change, an
import, or on demand:

1. Code components for every job.
2. Embeddings (`gemini-embedding-2`, 768 dims) for the profile and the **eligible** jobs, best
   first, at most `EMBEDDING_MAX_JOBS_PER_RUN` per run.
   - This deliberately deviates from "embed everything": ineligible jobs are hidden by default and
     never sent to the LLM, and free-tier quotas allow only about 40 job texts a minute.
   - Vectors are cached per user by content hash. If the quota runs out mid-run, the remaining
     jobs use code-only similarity this run and are filled in later.
   - Similarity is mapped to 0–100 between `SIMILARITY_FLOOR` (0.6) and `SIMILARITY_CEILING` (0.9),
     because unrelated text still scores about 0.65 with this model.
3. The top `llm_top_n` (default 10) eligible jobs are sent to the job-match prompt. Results are
   cached by (profile facts hash, job content hash, prompt version, model), so changing weights
   never triggers new calls.
4. Code re-checks the LLM output (`services/matching/refine.py`):
   - A skill is `demonstrated` only when code finds it in the verified profile (skills, verified
     bullets, project technologies). The LLM cannot create `demonstrated`.
   - `related` requires naming a real profile skill, and the LLM may downgrade.
   - Extra skills must appear in the job text.
   - Project relevance counts only with a real project name.
5. The explanation is shown as "AI-written summary" next to the code breakdown. Without AI, a
   code-written summary is used.

Observed on the free tier (2026-10-06): a 218-job search took about 30 seconds end to end, with
38 embeddings and 10 match calls of roughly 2,100 tokens each.

## Resume tailoring (Phase 6): how AGENTS.md §3 is enforced

`services/tailoring/` turns a verified profile into a `ResumeDocument` in which every skill, role,
bullet and project carries the `source_span` of the resume text it came from. For one job it
proposes `Change`s, which the user must accept one by one.

| Change | Source | New claims? | Checks |
|---|---|---|---|
| Reorder skills (and drop irrelevant ones) | rules, AI | No | ids must be real profile skills |
| Reorder bullets within a role | rules, AI | No | ids must belong to that role |
| Reword a bullet | AI | Possibly | code checks + second AI pass |
| 1–2 sentence summary citing item ids | AI | Possibly | citations required + code checks + second AI pass |

1. **Code checks** (`checks.py`). A rewrite may not:
   - add a number;
   - mention a technology absent from the same role's verified text (a skill from another role
     would invent a responsibility);
   - grow more than about 1.6× the original length.

   Summary sentences must cite real items, and every number or technology must appear in those
   items.
2. **The second pass** (`tailor_verify`) is shown each original and rewrite and must confirm
   that nothing new is claimed (scope, leadership, outcomes, …). It only sees changes that passed
   the code checks. If it can't run, rewrites are marked unverifiable.
3. **Unsupported changes** (failed by either layer) are shown with their reasons, can't be
   accepted (the API refuses with 422), and `apply()` skips them even if marked accepted.
4. **Approval and save.** Nothing is applied until accepted. Saving re-runs the code checks,
   stores the document and makes the version immutable. Rewritten bullets keep `original_text`,
   `source_span` and `ai_changed`, and the editor highlights them.
5. **Skill gaps.** Job skills the resume lacks (`related`/`not_demonstrated`) are listed beside the
   editor and never written into the resume.
6. **Without AI** (no consent or provider), only rule-based reordering is offered.

Downloads are built on the server and keep the format of the uploaded resume:

- **PDF** (`tailoring/pdf_render.py`): the original PDF's layout is read with pdfplumber
  (`resume/layout.py`: lines of styled pieces at their positions, rules, links). Unchanged lines
  are redrawn where they were; only accepted changes (reworded bullets, bullet order, summary,
  skill order) are re-wrapped in their paragraph's style, keeping its bold and italic phrases.
  Fonts are Latin Modern (`app/assets/fonts`, GUST Font License), the open version of the LaTeX
  font, with slight horizontal fitting for other fonts. No browser header or footer.
- **DOCX** (`tailoring/docx_inplace.py`): a Word upload is edited in place (paragraphs matched by
  text, runs rebuilt with the original formatting).
- If the upload was plain text, or a change can't be located in the original (e.g. the profile's
  bullet was edited by hand), a classic one-column template is used instead
  (`render_template_pdf`, `docx_render.py`). The log records `resume_layout_fallback` with the kind
  of change, never its text.

## Cover letters (Phase 7)

A letter is paragraphs of tagged sentences (`services/cover_letters/`). Each sentence is checked
according to its kind:

| Kind | Must | Code checks (`checks.py`) | Second AI pass |
|---|---|---|---|
| `claim` (about the candidate) | cite resume item ids | every number and technology appears in the cited items; citations must be real | is everything stated in the cited text? |
| `company` (about the employer or role) | quote the posting verbatim | the quote is found in the posting; numbers and technologies come from the quote | does the quote state it? |
| `connective` (greeting, transition, closing) | state no facts | no numbers, no technologies | does it state any fact? |

- **Unsupported sentences** (failed by either layer) are shown with reasons, excluded, and can't be
  included (the API refuses with 422). If the second pass can't run, AI sentences can't be used.
- **Your words.** When the user edits or adds a sentence, it is labeled "Your words" and not
  machine-checked: the user is its author.
- **Save** re-checks every machine-written sentence that is included, then freezes the letter.
- **Without AI**, a template letter is built in code: verified bullets in the first person
  ("As {title} at {company}, I {bullet}"), and the skills the job asks for that the resume shows.
  These go through the same checks.
- **Optional base:** a saved tailored resume version.

## Truthfulness guarantees

1. **Evidence on every item.** The LLM must quote `evidence` verbatim. `EvidenceValidator`
   (`services/resume/evidence.py`) finds each quote in the extracted text. It tolerates only
   case, whitespace and dash/quote style differences, and computes `source_span` offsets in code.
   The LLM never supplies spans.
2. **The quote must support the claim.** A skill name must appear in its quote (word-bounded,
   with a small alias table such as AWS ↔ Amazon Web Services). The title and company must be in
   the experience quote, and the institution in the education quote. Optional details (degree,
   field, project technologies and description) may also be supported by the item's own block:
   from its quote to the next item of the same kind or the next section heading (at most 600
   characters). Anything else is excluded.
3. **Unsupported claims are excluded.** Anything that fails becomes an `UnsupportedClaim`. It is
   shown to the user under "Not saved" and is never part of the profile's facts.
4. **Dates and experience are computed in code** (`utils/dates.py`) from quoted date text.
   Overlapping roles are counted once.
5. **User edits are labeled.** Items the user adds are `source: "user"` and have no span. When a
   profile is saved, the server re-verifies every `source: "resume"` item against the resume
   text and recomputes spans. An edit that changes a resume-sourced claim is rejected (422).

## Safety

- **Untrusted data.** Resume text sits between `<resume_text>` tags. Tag look-alikes inside the
  text are neutralized. The system prompt says the content is data and must not be followed.
  Output is only ever parsed into `ResumeExtraction`, and nothing in it can trigger an action.
- **Consent.** No resume text is sent unless `settings.llm_consent` is on. Tests assert that the
  provider is never called otherwise.
- **Budget.** `LLM_MONTHLY_TOKEN_BUDGET` is a hard per-user cap per calendar month, checked before
  every call with a conservative estimate. Every attempt, including failures, is recorded in `llm_usage`.
- **Rate limit.** Upload and re-parse are limited per user (`AI_RATE_LIMIT` per `AI_RATE_WINDOW_SECONDS`).
- **Cache.** `ai_extractions` stores validated output per user, keyed by
  `(task, sha256(text), PROMPT_VERSION, model)`, so identical text is never sent twice. Bump
  `PROMPT_VERSION` whenever the prompt or schema changes.
- **Logging.** Events (`llm_call_completed`, `llm_call_failed`, `llm_output_invalid`,
  `llm_budget_exceeded`, `resume_parse_*`) carry IDs, counts, tokens and durations, never resume text.

## Testing

Tests never call a real LLM. `FakeAIProvider` replays queued responses and records calls.
Fixtures live in `tests/fixtures/ai/resume_extraction/`:

- `*.gemini.json`: real responses recorded from `gemini-3.5-flash-lite` with prompt v2 on the
  fictional resumes. Tests assert that they verify with zero unsupported claims.
- `sneha_backend.invented_claims.json`: hand-written adversarial output (Kubernetes, a fake
  bullet, Redis, "Go") that must be excluded.

To re-record after changing the prompt or schema, run the extraction once against the fictional
resumes and save `response.text`. Never record from a real person's resume.
