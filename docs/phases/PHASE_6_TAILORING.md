# Phase 6 — Resume tailoring and versioning

Read `AGENTS.md` first, especially §3 (truthfulness). Written from the plan proposed at the end
of Phase 5, which the owner approved.

## Goal

For a specific job, propose honest improvements to the user's resume. The user approves each
change, and approved changes become a saved, downloadable resume version linked to that job.
Nothing is ever claimed that the verified resume doesn't support.

## What tailoring may change (AGENTS.md §3)
- Reorder skills and drop irrelevant ones (only skills already on the verified resume).
- Reorder bullets within a role and drop irrelevant ones.
- Reword a bullet for clarity, use a stronger verb, or use the job's wording, **only for things
  that bullet or its role already says**.
- An optional 1–2 sentence summary in which every sentence cites the resume items it rests on.

It never adds projects, employers, metrics, certifications, technologies or responsibilities.
Related skills are never presented as demonstrated.

## Enforcement (all required)
1. **Source spans.** Every item in a tailored resume keeps the `source_span` of the verified resume
   text it comes from. Rewritten bullets keep their original's span and text.
2. **Code checks** on every AI rewrite and summary sentence:
   - Every number must appear in the source text.
   - Every technology or skill must appear in the same role's verified text (or, for a summary,
     in the cited items).
   - The rewrite may not grow much longer than the original.
   - References must point to real items.
3. **A second validation pass by AI.** Separately, the AI is shown each original and rewrite and
   flags any claim the original doesn't support.
   - Anything flagged by code or AI is marked `UNSUPPORTED`: shown with the reason, impossible to
     accept, and excluded from saved versions.
   - If the second pass can't run, rewrites can't be accepted.
4. **Labeled changes and approval.** Every change is labeled "AI suggestion" or "Rule-based".
   Nothing is applied until the user accepts it, and a version is saved only on request.
   Code checks run again on save.
5. **Skill gaps** are shown as `related` or `not_demonstrated` next to the editor, never in the
   resume itself.

Without AI consent or a configured provider, tailoring still works with rule-based changes only
(skills and bullets reordered by relevance to the job), with no rewrites.

## Deliverables
- `resume_versions`:
  - Linked to user, profile version, job (`SET NULL`) and a per-user version number.
  - Status `generating` | `ready` | `failed` | `saved`.
  - The proposed changes with their decisions, and the saved document (immutable once saved).
- Worker task for generation: AI suggestions, then code checks, then the AI verification pass,
  combined with the rule-based changes.
- API: `POST /api/tailoring` (job), list, get (with a live preview of the current decisions),
  set decisions, save, delete, DOCX download.
- UI:
  - "Tailor resume" on job and application pages.
  - `/tailoring` lists versions.
  - `/tailoring/[id]` shows changes with before/after, labels, unsupported reasons,
    accept/reject, a live preview and skill gaps.
  - Save, then download DOCX or print to PDF from a clean single-column page that ATS systems
    can read.
- Export and delete cover resume versions.

## Definition of Done
- [ ] `make check` passes; migrations upgrade and downgrade
- [ ] Unit tests for every check: invented number, technology from another role, length
      inflation, bad references, summary citations, verifier flags, verifier unavailable
- [ ] Integration tests with a fake AI that deliberately invents claims:
  - they are UNSUPPORTED and can't be accepted
  - the saved version excludes them, keeps spans and never lists related skills
  - saved versions are immutable
  - DOCX opens and contains the approved text
  - the rule-based path makes no AI calls
  - per-user isolation, export and delete work
- [ ] No test calls a real LLM
- [ ] Running in Docker with Gemini: tailor a real job, review, accept, save, download
- [ ] Docs updated (AI.md truthfulness section)
