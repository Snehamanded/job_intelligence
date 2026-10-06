# Job Source Feasibility Matrix

This is a starting assessment, written from general knowledge. **Before building any connector, verify the source's current API docs, terms of service and robots.txt**, and record the date and findings in the "Verified" column. Terms change.

## Tiers

| Tier | Meaning | What to build |
|---|---|---|
| **A** | Official public API or documented public feed | Real connector |
| **B** | Public feed or structured data (RSS, JSON-LD, sitemap), no API contract | Real connector, with polite rate limits and robots.txt checks |
| **C** | Partner-only API, or terms restrict automated access | Interface + mock + manual import. No scraping |
| **D** | Not worth integrating | Skip |

## ATS platforms (company career portals)

These are the best real sources: they list jobs first, with no stale reposts, and one adapter covers many companies.

| Source | Tier | Access | Notes | Verified |
|---|---|---|---|---|
| Greenhouse | A | Public Job Board API per company board token (`boards-api.greenhouse.io`) | Unauthenticated GET for published jobs. **Built in Phase 3** | 2026-10-05: docs confirm unauthenticated GET for list/job/board; robots.txt disallows only `/embed/`; no published rate limit (we pause 1s between boards, cap 25 boards). Pay usually in description text; `pay_input_ranges` often empty. See `docs/CONNECTORS.md` |
| Lever | A | Public Postings API per company (`api.lever.co/v0/postings/{company}`) | JSON output | |
| Ashby | A | Public job posting API per job board name | JSON output | |
| SmartRecruiters | A | Public Posting API per company identifier | Check pagination limits | |
| Workday | B/C | No official public API. Career sites use internal JSON endpoints that differ per tenant | Undocumented, may break or be restricted per tenant. Defer; review terms per company before using | |
| iCIMS | B | Per-tenant. Some expose feeds or JSON-LD | No uniform API | |
| Taleo | B | Per-tenant, inconsistent | Low priority | |
| SAP SuccessFactors | B | Per-tenant, inconsistent | Low priority | |
| Custom career pages | B | `JobPosting` JSON-LD (schema.org), sitemap.xml, RSS | Generic structured-data adapter. Check robots.txt first | |

## Remote job boards

| Source | Tier | Access | Notes | Verified |
|---|---|---|---|---|
| Remote OK | A | Public JSON API | Terms ask for attribution/link-back to the listing. Honor it | |
| We Work Remotely | B | RSS feeds by category | Link back to source | |
| Remotive | A | Public API | Documented request-rate guidance and attribution. Cache aggressively | |
| Himalayas | A/B | Public API or feed (confirm) | Verify availability and terms | |
| Jobspresso | B | RSS (confirm) | Verify | |

## Aggregator APIs (not in the original spec, worth evaluating)

These give broad coverage, including India, without scraping job boards. Most need a free API key.

| Source | Tier | Notes | Verified |
|---|---|---|---|
| Adzuna API | A | Has country endpoints (India included). Key required | |
| Jooble API | A | Key required | |
| Arbeitnow API | A | Mostly Europe, remote-friendly | |
| HN "Who is hiring" (via Algolia HN API) | A | Monthly thread, good for startups. Needs LLM extraction | |

## General job boards

| Source | Tier | Reality | What to do |
|---|---|---|---|
| LinkedIn | C | No public job search API for individuals; partner program only. Terms prohibit scraping | Mock + manual import + parse user-forwarded job alert emails |
| Indeed | C | Public job-search API not generally available; terms restrict automated access | Mock + manual import. Revisit only with an official partner agreement |
| Glassdoor | C | API closed to new partners; restrictive terms | Mock + manual import |
| ZipRecruiter | C | Partner/affiliate access | Mock until you have partner access |
| Google Jobs | C | No public search API. (Google's Talent API is for employers.) | Don't scrape results. Instead read `JobPosting` JSON-LD from company pages, which is what Google Jobs itself indexes |

## India boards

| Source | Tier | Reality | What to do |
|---|---|---|---|
| Naukri | C | No public API; terms restrict automation; bot protection | Mock + manual import + email alerts |
| Foundit | C | Same | Same |
| Shine | C | Same | Same |
| Apna | C | Same | Same |

## Startup / tech boards

| Source | Tier | Reality | What to do |
|---|---|---|---|
| Wellfound | C | No public API; strong bot protection | Mock + manual import |
| Instahyre | C | No known public API | Mock + manual import |
| Cutshort | C | No known public API | Mock + manual import |
| Hirist | C | No known public API | Mock + manual import |

## Always-available fallbacks (legal and robust)

1. **Manual import:** user pastes a job URL or the description text. The app parses and normalizes it, then scores it like any other job.
2. **Email alert ingestion:** user forwards job-alert emails from LinkedIn, Naukri and others. Parse the job links and snippets from the email, with the user's consent.
3. **Browser bookmarklet or extension (later):** user clicks "Save to my CRM" on a page they are viewing. It captures the page they are already on. It does not crawl.
4. **Company watchlist:** a config of `company -> careers URL -> ATS type -> board token`. This is the highest-quality source for target companies.

## Connector build order

1. Greenhouse (Phase 3, validates normalization on real data)
2. Manual import
3. Lever, Ashby, SmartRecruiters (Phase 8)
4. Remote OK, We Work Remotely, Remotive
5. Adzuna / Jooble (broad India coverage)
6. JSON-LD career-page adapter
7. Email alert ingestion
8. Workday and other per-tenant ATS, after a terms review

## Per-connector checklist (copy into each connector's PR)

- [ ] Official API or feed documented, with link
- [ ] robots.txt checked, date recorded
- [ ] Terms reviewed, date recorded
- [ ] Rate limit and User-Agent configured
- [ ] Attribution/link-back handled if required
- [ ] Maps to the common job schema; unmapped fields preserved in `raw_payload`
- [ ] Failure returns a source-level error status and never throws through the orchestrator
- [ ] Tests run against recorded fixtures, not the live site
