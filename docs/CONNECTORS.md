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
   means the job was already found elsewhere.
3. Otherwise the same description hash counts as a duplicate **only if the places match**. Employers
   such as Palantir post one description in several cities, and those are separate openings.
4. Anything else is a new job. For duplicates, the new source is appended to `also_seen_on`.

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

| Source | Kind | Config | Notes |
|---|---|---|---|
| Greenhouse | Real (A) | Board token | `boards-api.greenhouse.io`. Token validated on add. 1s between boards |
| Lever | Real (A) | Site name | `api.lever.co/v0/postings/{site}?mode=json`, paged 100 at a time with a 1s crawl delay (robots.txt). No company name in the API, so the user's display name (or the site name) is used |
| Ashby | Real (A) | Board name | `api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true`. Pay used only when `shouldDisplayCompensationOnJobPostings` is true. The primary location follows `workplaceType`; secondary ones keep their own wording ("Remote (Canada)") |
| Remote OK | Real (A) | On/off | `remoteok.com/api`. The first element is the legal notice. Links are **followed** (no `nofollow`) and shown as "Source: Remote OK", as their terms require. No logo. At most hourly per user. Salary fields are USD per year; 0 means not listed |
| Remotive | Real (A) | On/off | `remotive.com/api/remote-jobs`, one request then filtered locally. At most once every 6h per user (they ask for 4 or fewer a day). Link back plus "Source: Remotive" |
| Adzuna | Real (A), keyed | Country | Off until `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` are set. `salary_is_predicted` salaries are ignored. Descriptions are snippets. Built from the docs; not live-verified |
| We Work Remotely | Real (B) | On/off | `weworkremotely.com/remote-jobs.rss`, parsed with `defusedxml` (`connectors/rss.py`). Title is "Company: Role"; "Anywhere in the World" → Worldwide. At most hourly |
| Jobspresso | Real (B) | On/off | `jobspresso.co/jobs/feed/` (the query-string feed is disallowed by robots.txt). `dc:creator` is "Company<br>⚲ Location". At most hourly |
| Himalayas | Real (A) | On/off | `himalayas.app/jobs/api/search?q=…&country=India`, up to 3 pages of 20 for up to 3 keywords. Salary only when `salaryPeriod` is known. At most every 6h |
| Workday, SmartRecruiters, iCIMS, Taleo, SAP SuccessFactors | Import (B) | — | No search connector. A pasted job link is read from its JobPosting data (robots.txt checked) and labeled with the platform (`importer.platform_of`). The SmartRecruiters API host is never fetched |
| Google Jobs | Import (C) | — | No API; google.com is never fetched. Import the company's own page instead |
| LinkedIn, Indeed, Glassdoor, ZipRecruiter, Naukri, Foundit, Shine, Apna, Wellfound, Instahyre, Cutshort, Hirist | Mock (C) | — | Never fetched. Fictional jobs only when `ENABLE_MOCK_CONNECTORS=true`, labeled "Mock data". Paste descriptions to import real ones |

The Sources page lists every source grouped by category (company career portals, remote, general,
India, startup/tech) with how it's supported.

Minimum intervals are enforced from `job_source_configs.last_fetched_at`. A skipped source shows
"Checked recently … next checked in N min" in the search results.

## Manual import

`POST /api/jobs/import` with a URL:

1. **Tier C sites** (LinkedIn, Naukri, Indeed, Glassdoor, Wellfound, Google, the SmartRecruiters API…) are refused
   without fetching anything. The user pastes the description instead.
2. **Greenhouse, Lever and Ashby job links** go through their APIs.
3. **Any other page** goes through `SafeFetcher`, then `jsonld.find_job_postings` (schema.org
   `JobPosting`, including `@graph`, comment-wrapped scripts, `TELECOMMUTE`, `baseSalary`). The
   fetcher only proceeds when:
   - the scheme is http(s), there are no credentials in the URL, and the port is 80 or 443;
   - every resolved address is public (`ip.is_global`; IPv4-mapped IPv6 unwrapped; loopback,
     private, link-local, metadata, multicast and reserved addresses refused, which covers decimal
     and octal IP forms after resolution);
   - each redirect passes the same check again, up to 3;
   - the response is HTML and at most `IMPORT_MAX_BYTES` (2 MB);
   - robots.txt allows our User-Agent.

   Residual risk: DNS can change between the check and the connection (rebinding). This is
   acceptable for a single-user app, and the address checks still block simple tricks.

## Bulk import: alert emails and WhatsApp

`POST /api/job-imports {channel: email | whatsapp | other, text}` queues a background import
(`services/jobs/bulk_import.py`); `GET /api/job-imports/{id}` shows its progress and results.
This is how jobs from sites that can't be fetched (LinkedIn, Naukri, Indeed alerts; WhatsApp
groups and channels) get in: the user pastes what they already received.

- WhatsApp chat exports (Android and iOS formats) are split into messages; timestamps, sender
  names and numbers, system notices and media placeholders are removed before anything else.
  WhatsApp itself is never accessed: there is no official API for reading channels, and automating
  WhatsApp Web would break its terms and AGENTS.md §2.
- Posts are found by the LLM (with consent) or by rules (email: blocks ending at a link; chat: one
  message per post, kept when it names a role and has a link or hiring words).
- A post's link is imported in full when it's a company career page (Greenhouse, Lever, Ashby or
  JobPosting data), at most 15 per batch with the usual delay. LinkedIn, Naukri and other Tier C
  links are stored for the user to open, never fetched, including after redirects from short links.
- Otherwise the post's own text is the description (`source` = `email_alert`, `whatsapp` or
  `pasted`), deduplicated like any job. Short posts are flagged so the user can paste more.
- Up to 60,000 characters per import (the newest messages of a long chat export); the pasted text
  is deleted once processed.

## Adding a connector

1. Verify the API, terms and robots.txt, and record them in SOURCE_FEASIBILITY.md.
2. Implement `JobConnector` in `app/connectors/<name>.py` with `make_client`.
3. Register it in `connectors/registry.py` (`build_connectors` and `describe`).
4. Record a small real payload under `tests/fixtures/<name>/` and test it through
   `httpx.MockTransport`. Tests never touch the network.
