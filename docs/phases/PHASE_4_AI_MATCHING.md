# Phase 4 — AI matching

Read `AGENTS.md` first (§5 scoring design). Written from the plan proposed at the end of Phase 3,
which the owner approved.

## Goal

Every job gets a 0–100 match score with a breakdown, skill-by-skill evidence and a short
explanation. Jobs are ranked by match, freshness, salary fit and the user's own priority, so the
user mostly sees the best ~30.

## Design

### What is computed where
| Component (default weight) | How |
|---|---|
| Skills (30) | Job skills come from a curated vocabulary found in the job text, plus profile skills mentioned there. Each is labeled `demonstrated` / `related` / `not_demonstrated` against the **verified** profile, in code. For the top N jobs the LLM may refine the labels; code re-checks them, and the LLM can never upgrade a skill without a real profile skill backing it |
| Experience (20) | Code: candidate months vs the job's stated min/max |
| Role (20) | Code: title match against target roles and past titles, blended with embedding similarity when available |
| Location/remote (10) | Code: from the eligibility location check |
| Projects (10) | LLM for the top N (relevance of the user's verified projects). Otherwise a code overlap of project technologies with the job text |
| Industry (5) | LLM for the top N. Otherwise neutral (50, marked unknown) |
| Preferences (5) | Code: employment type and salary checks |

- **Ranking:** `rank = 0.70*match + 0.10*freshness + 0.10*salary_fit + 0.10*user_priority`. All
  weights are configurable.
- **High priority:** eligible and match ≥ 85.
- **Bands:** 90+ Excellent, 80–89 Strong, 70–79 Good, 60–69 Moderate, below 60 Weak.

### Cost control
- Profile and job texts are embedded (`gemini-embedding-2`, 768 dimensions, stored in pgvector)
  and cached by content hash per user.
- Jobs are ranked by the deterministic score blended with similarity. Only the top N eligible
  jobs (default 10) are sent to the LLM.
- LLM match results are cached by (profile content hash, job content hash, prompt version,
  model). Changing weights never triggers new LLM calls.
- Everything needs AI consent plus a configured provider. Without them the whole pipeline runs
  in code (lexical similarity), and the UI says so.

### Versioning
- `job_matches` rows are keyed by `(job, profile_version, scoring_config_version)`.
- `scoring_configs` are versioned per user.
- A new profile version (re-parse, edit, preferences) or config version means old rows simply
  stop being current. Rescoring runs in the worker after a search, a parse, a profile/config
  change, an import, or on demand.

### Truthfulness and safety
- The match prompt receives only verified profile items and the job text as delimited, untrusted
  data. Output is validated with Pydantic.
- A skill is `demonstrated` only when code finds it (or an alias) in the verified profile skills.
  `related` needs a named related profile skill. Related is never shown as demonstrated.
- The explanation is labeled "AI-written" and shown next to the code-computed breakdown. It falls
  back to a code-written summary.

## Deliverables
- Migration: `embeddings` (pgvector), `scoring_configs`, `job_matches`, `jobs.priority`.
- `AIProvider.embed` for Gemini/OpenAI/fake. A shared LLM runner (consent, budget, cache, retry,
  usage), reused by resume extraction.
- `services/matching/`: skill vocabulary and relations, components, ranking, embeddings,
  LLM refinement, a `MatchingService` that upserts current rows.
- API:
  - `GET /api/jobs` gains `sort=rank|newest`, `high_priority_only`, and match summaries.
  - `GET /api/jobs/{id}` gains the full match.
  - `PATCH /api/jobs/{id}` sets priority.
  - `GET/PUT /api/scoring-config`.
  - `POST /api/matches/rescore` and `GET /api/matches/status`.
- UI:
  - Jobs list ranked, with score and label badges.
  - Job page with the breakdown, skills table, explanation and priority control.
  - Ranking weights on Preferences.
  - Dashboard high-match jobs.

## Definition of Done
- [ ] `make check` passes; migrations upgrade and downgrade
- [ ] Unit tests: each component, ranking, bands, skill status rules (an LLM can't upgrade skills),
      config validation, embedding cache
- [ ] Golden set: 2 resumes × 5 jobs with expected rank order (deterministic path)
- [ ] Integration tests: scoring after a search; version invalidation (profile edit, config change);
      top-N limit and LLM cache (fake provider); no-consent path makes no AI calls
- [ ] No test calls a real LLM or embedding API
- [ ] Running in Docker with Gemini: real jobs scored and ranked, top N with AI explanations
- [ ] Docs: AI.md and ARCHITECTURE.md updated
