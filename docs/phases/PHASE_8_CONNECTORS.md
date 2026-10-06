# Phase 8 — More real connectors

Read `AGENTS.md` (§8) and `docs/SOURCE_FEASIBILITY.md` first. Written from the plan proposed at the
end of Phase 7, which the owner approved. Each source was verified on 2026-10-06; the results are
recorded in SOURCE_FEASIBILITY.md.

## Verification outcome

| Source | Decision |
|---|---|
| Lever | Real connector (per company site). robots allows, crawl-delay 1s |
| Ashby | Real connector (per job board). Compensation only when the employer shows it |
| Remote OK | Real connector (global feed). Dofollow link back plus "via Remote OK"; at most hourly |
| Remotive | Real connector (global feed). Link back plus "via Remotive"; at most every 6h per user |
| Adzuna | Real connector behind server keys (off by default). Predicted salaries ignored. Not live-verified |
| SmartRecruiters | **Not built.** robots.txt disallows all agents but LinkedInBot. Stays Tier C: mock plus manual import |
| Jooble | Deferred (low value relative to Adzuna) |
| Career pages | Single-URL import of `JobPosting` JSON-LD, respecting robots.txt and guarded against SSRF. No crawling |

## Deliverables
- **Connectors** for Lever, Ashby, Remote OK, Remotive and Adzuna, built on the existing
  interface: independent failure, a clear User-Agent, timeouts and pauses between requests.
- **Normalization:**
  - Structured salary, employment type and location from each source when present; text parsing
    otherwise.
  - Remote feeds become "Remote (region)" ("USA Only" becomes United States).
- **Source configuration:**
  - Per-company boards for Greenhouse, Lever and Ashby (validated on add, with an optional
    display name).
  - On/off switches for Remote OK, Remotive and Adzuna.
  - `last_fetched_at` per source config enforces each source's minimum interval; a skipped source
    says why.
- **Attribution:** "via {source}" on cards; Remote OK links without `nofollow`; no logos.
- **Manual import:**
  - Greenhouse, Lever and Ashby job URLs go through their APIs.
  - Any other URL goes through the JSON-LD importer:
    - only http(s) and default ports;
    - the hostname must resolve only to public IPs (no loopback, private, link-local or
      metadata ranges, and no IPv4-mapped tricks), re-checked on every redirect, with at most 3
      redirects;
    - responses must be HTML and at most 2 MB, with timeouts;
    - robots.txt must allow our User-Agent.
- **Tests:**
  - Recorded, trimmed real payloads for Lever, Ashby, Remote OK and Remotive, and a fixture
    shaped from Adzuna's docs.
  - JSON-LD fixtures, SSRF unit tests, interval-skip tests, isolation.
  - No network.
- **Docs:** CONNECTORS.md and SOURCE_FEASIBILITY.md.

## Definition of Done
- [ ] `make check` passes; migration up/down
- [ ] Connector tests on recorded payloads; normalization of structured salary, remote and
      employment; predicted Adzuna salary ignored
- [ ] Minimum-interval enforcement; attribution in the UI
- [ ] SSRF tests: private, loopback, link-local and metadata addresses; IPv6 loopback; decimal or
      odd IP forms; redirect to a private address; non-http schemes; robots disallow
- [ ] Running in Docker: real Lever, Ashby, Remote OK and Remotive searches, and a career-page
      import
