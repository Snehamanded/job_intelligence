# Phase 7 — Cover letters

Read `AGENTS.md` first, especially §3. Written from the plan proposed at the end of Phase 6, which
the owner approved.

## Goal

Draft a cover letter for a job that says only true things: about the candidate, only what the
verified resume supports; about the company, only what the job posting says. The user edits and
approves, then downloads.

## Sentence model
A letter is paragraphs of sentences. Every sentence has a kind:

| Kind | Meaning | Must | Checks |
|---|---|---|---|
| `claim` | About the candidate | Cite resume item ids | Numbers and technologies must appear in the cited items; then the second AI pass |
| `company` | About the employer or role | Quote the job posting verbatim | The quote must be found in the posting; numbers and technologies must be in the quote; then the second AI pass |
| `connective` | Greeting, transition, closing | Make no factual claim | No numbers or technologies; the second AI pass confirms it states no facts |

- Sentences failing any check are `UNSUPPORTED`: shown with the reason, excluded, and impossible
  to include.
- If the second pass can't run, AI sentences can't be included.
- Sentences the user writes or edits are labeled "Your words" and are not machine-checked. The
  user is the author of those.
- Without AI consent or a provider, a template letter is built in code: verified bullets in the
  first person, and skills the job asks for that the resume shows.

## Deliverables
- `cover_letters` table:
  - Linked to user, profile version, job (`SET NULL`) and an optional saved tailored resume
    version, with a per-user version number.
  - Tone (`professional` | `warm` | `concise`), length (`short` | `medium`), status
    (`generating` | `ready` | `failed` | `saved`), method, sentences (JSONB) and the saved content
    (immutable).
- Prompts `cover_letter` and `cover_letter_verify`, the code checks, the template builder, and a
  worker task.
- API: create, list, get (with a preview), edit sentences (include, rewrite, add your own), save,
  delete, DOCX.
- UI:
  - "Write cover letter" on job and application pages.
  - `/cover-letters` lists letters.
  - The editor shows labels, citations or quotes, unsupported reasons, include toggles, inline
    edit and a live preview. Save, then DOCX or print to PDF.
- Export and delete cover letters.

## Definition of Done
- [ ] `make check` passes; migrations upgrade and downgrade
- [ ] Unit tests: claim citations, numbers and technologies; a company quote missing from the
      posting; a connective that sneaks in a claim; template sentences pass the checks
- [ ] Integration tests with a fake AI that invents claims:
  - unsupported sentences can't be included
  - the second pass flags claims
  - the second pass being unavailable blocks AI sentences
  - edits are labeled as the user's words
  - the saved letter excludes unsupported sentences and can't be changed
  - the DOCX opens
  - the template path makes no AI calls
  - isolation, export and delete work
- [ ] No test calls a real LLM
- [ ] Running in Docker with Gemini: generate, edit, save, download
- [ ] Docs updated
