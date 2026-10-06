# Connectors

How jobs get into the app. Source tiers and terms are in
[SOURCE_FEASIBILITY.md](SOURCE_FEASIBILITY.md). Check a source's docs, terms and robots.txt
before building its connector, and record what you found there.

## Interface

`app/connectors/base.py`:

```python
class JobConnector(Protocol):
    name: str            # "greenhouse"
    label: str           # "Greenhouse"
    tier: "A" | "B" | "C"
    is_mock: bool
    needs_targets: bool  # needs per-user config such as board tokens

    def fetch(self, query: SearchQuery, report: FetchReport) -> Iterator[RawPosting]: ...
```

- `fetch` yields `RawPosting`s (title, company, location text, **plain-text** description, URL,
  posted time, optional structured salary, raw payload).
- It raises `ConnectorError` (with a message safe to show the user) when the source can't be used
  at all. Problems with individual targets go into `report.errors`, and that source is reported
  as `partial`.
- Connectors never normalize, dedupe or store. `services/jobs/` does that, the same way for every
  source.
- HTTP goes through `connectors/http.make_client()`: a clear `User-Agent` (`CONNECTOR_USER_AGENT`),
  timeouts, no redirects and no cookies.

## Isolation

`SearchService` runs each connector in its own try/except and commits after each one. A
`ConnectorError` or any unexpected exception marks only that source `failed` in
`search_runs.source_results`, and the search carries on with the others. Every source
records: status, fetched, kept (title matched), new, updated, duplicates, error and duration.
Log events: `search_started`, `source_completed`, `source_failed`, `duplicates_removed`,
`search_completed`.

## Normalization and dedupe (no LLM)

| Field | Where | Notes |
|---|---|---|
| Location, remote | `services/jobs/normalize.parse_location` | Multi-location strings, office suffixes ("Bengaluru-VTP"), remote regions ("Remote, Canada; Remote, US") |
| Employment type | `detect_employment_type` | From the title first, then explicit phrases. Otherwise `unknown` |
| Salary | `utils/salary.parse_salary` | Needs a currency and pay context. k/L/LPA/Cr, ranges, periods. Ambiguous text is unknown. **Never guessed** |
| Experience | `utils/experience.parse_experience` | "3+ years", "1–2 years", "minimum 2 years". Must mention experience in the same sentence |
| Description | `utils/html_text.html_to_text` | Stored and shown as plain text only |

`JobStore.save` checks for duplicates in this order:
1. The same `(source, source_job_id)` is updated in place.
2. Otherwise the same `dedupe_key` (company without suffixes + title + first place + remote type)
   or the same description hash means the job was already found elsewhere. The new source is
   appended to `also_seen_on`.
3. Anything else is a new job.

## Eligibility

`services/jobs/eligibility.evaluate(job, preferences, experience_months)` checks employment
type, location/remote, salary floor and experience. Each check returns `pass`, `fail` or
`unknown` with a reason. A job is eligible unless a check fails. Rules:

- `remote_scope=india` accepts remote roles open in India. `worldwide` also accepts
  Worldwide/APAC. Remote roles limited to other countries fail. Remote with no stated region is
  `unknown`.
- Salary is only compared in the same currency, annualized from the stated period. Unknown salary
  or another currency is `unknown`, or `fail` if `salary_unknown_policy=exclude`.
- Experience fails only when the job's minimum is more than 2 years above the candidate's.

## Sources

| Source | Kind | Notes |
|---|---|---|
| Greenhouse | Real (Tier A) | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`. Users add board tokens on `/jobs/sources`, and each token is validated against `/v1/boards/{token}`. 1s pause between boards, at most 25 boards and 1,000 jobs per search. Single jobs (manual import) use `.../jobs/{id}?pay_transparency=true` |
| LinkedIn, Naukri, Indeed | Mock (Tier C) | Fictional jobs, only when `ENABLE_MOCK_CONNECTORS=true`, always labeled "Mock data". No scraping |
| Manual import | Universal | A Greenhouse job URL is fetched through the API. Any other job can be pasted (title, company, location, description) |

## Adding a connector

1. Verify the API, terms and robots.txt, and record them in SOURCE_FEASIBILITY.md.
2. Implement `JobConnector` in `app/connectors/<name>.py` with `make_client`.
3. Register it in `connectors/registry.py` (`build_connectors` and `describe`).
4. Record a small real payload under `tests/fixtures/<name>/` and test it through
   `httpx.MockTransport`. Tests never touch the network.
