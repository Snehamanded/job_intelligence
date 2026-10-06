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
| Lever | A | Public Postings API per company (`api.lever.co/v0/postings/{company}`) | JSON output. **Built in Phase 8** | 2026-10-06: docs (github.com/lever/postings-api) confirm unauthenticated GET of published postings, `mode=json`, skip/limit; robots.txt `Allow: /`, `Crawl-delay: 1`. No company name in payload; `salaryRange` optional |
| Ashby | A | Public job posting API per job board name | JSON output. **Built in Phase 8** | 2026-10-06: docs (developers.ashbyhq.com) confirm public `GET /posting-api/job-board/{name}?includeCompensation=true`; no stated rate limits (we pause 1s); robots.txt not served. Compensation used only when `shouldDisplayCompensationOnJobPostings` is true |
| SmartRecruiters | **C** API / B pages | Posting API is documented, but `api.smartrecruiters.com/robots.txt` disallows all agents except LinkedInBot | No search connector. **Job pages (jobs.smartrecruiters.com) importable by link** via their JobPosting data | 2026-10-06: API robots.txt `User-agent: * Disallow: /`; jobs.smartrecruiters.com serves no robots.txt, so single-page import is allowed. API host is on the no-fetch list |
| Workday | B (import only) | No official public API. Career sites use internal JSON endpoints that differ per tenant | Internal endpoints not used. **Import a job page by link**; robots.txt checked per tenant at import time; labeled "Workday" | 2026-10-06 |
| iCIMS | B (import only) | Per-tenant. Some expose JSON-LD | **Import by link** when the page publishes JobPosting data and robots.txt allows; labeled "iCIMS" | 2026-10-06 |
| Taleo | B (import only) | Per-tenant, inconsistent | **Import by link** as above; otherwise paste the description | 2026-10-06 |
| SAP SuccessFactors | B (import only) | Per-tenant, inconsistent | **Import by link** as above; otherwise paste the description | 2026-10-06 |
| Custom career pages | B | `JobPosting` JSON-LD (schema.org), sitemap.xml, RSS | Generic structured-data adapter. Check robots.txt first. **Phase 8: single-URL import** (robots.txt checked, SSRF-guarded); no crawling | 2026-10-06 |

## Remote job boards

| Source | Tier | Access | Notes | Verified |
|---|---|---|---|---|
| Remote OK | A | Public JSON API | Terms ask for attribution/link-back to the listing. Honor it. **Built in Phase 8** | 2026-10-06: robots.txt allows `/` (`Crawl-delay: 1`). API legal notice: link back to the Remote OK URL **without nofollow**, name Remote OK as source, don't use the logo. We: link without nofollow, show "via Remote OK", no logo, fetch at most hourly |
| We Work Remotely | B | Public RSS (`/remote-jobs.rss`) | Link back to source. **Built** | 2026-10-06: robots.txt allows the feed; terms page returned 403 (not read). One feed request per search, at most hourly; link back + "via We Work Remotely" |
| Remotive | A | Public API | Documented request-rate guidance and attribution. Cache aggressively. **Built in Phase 8** | 2026-10-06: github.com/remotive-com/remote-jobs-api: link back + mention Remotive; >2 req/min blocked; recommends ≤4 queries/day; jobs delayed 24h; don't resubmit to other job boards. robots.txt is behind a Cloudflare challenge (not read, not bypassed); API endpoint answers normally. We fetch at most once per 6h per user |
| Himalayas | A | Public JSON API (`himalayas.app/jobs/api/search`) | Link back + name Himalayas; don't resubmit to other boards. **Built** | 2026-10-06: docs allow use with link back and attribution; data refreshes daily; 20 per page. We search roles open to India, ≤3 pages × ≤3 keywords, at most every 6h |
| Jobspresso | B | Public RSS (`/jobs/feed/`) | **Built** | 2026-10-06: robots.txt disallows `/*?` (so no query-string feed) with Crawl-delay 3; `/jobs/feed/` allowed; terms say nothing on feeds. One request per search, at most hourly |

## Aggregator APIs (not in the original spec, worth evaluating)

These give broad coverage, including India, without scraping job boards. Most need a free API key.

| Source | Tier | Notes | Verified |
|---|---|---|---|
| Adzuna API | A | Has country endpoints (India included). Key required. **Built in Phase 8, off until keys are set** | 2026-10-06: docs (developer.adzuna.com/docs/search): `GET /v1/api/jobs/{country}/search/{page}` with app_id/app_key; descriptions are snippets; `salary_is_predicted=1` salaries are ignored (never guess). Terms/limits not public without registering: review at signup. Not live-verified (no keys); tests use a docs-shaped fixture |
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
| Google Jobs | C | No public search API. (Google's Talent API is for employers.) | Never fetched (google.com is on the no-fetch list). Import the company's own job page by link instead: its JobPosting JSON-LD is what Google Jobs indexes |

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
