# Phase 5 — Job CRM

Read `AGENTS.md` first. Written from the plan proposed at the end of Phase 4, which the owner
approved.

## Goal

Track every application from "saved" to an outcome, with notes, interviews and a history, then
learn from it: which sources and which match levels actually lead to interviews.
The user applies on the employer's site; nothing here submits anything (AGENTS.md §2).

## Deliverables

### Data
- `applications`:
  - Links to a job (nullable, `SET NULL`, so the application outlives a deleted job), plus a
    snapshot of title, company, location, URL and source.
  - The match score and label at the time of saving, used for analytics.
  - Stage: `saved` | `applied` | `interviewing` | `offer` | `rejected` | `withdrawn`.
  - `applied_at`, `closed_at`, a next action and its date, and the position in its board column.
  - One application per job per user.
- `application_events`: the history (created, stage changed, interview added, …) with from/to stage.
- `application_notes`: free-text notes.
- `interviews`: date and time, kind, place or link, outcome (`pending` | `passed` | `failed` |
  `cancelled`), notes, and a preparation checklist (`[{text, done}]`).

### Rules (code)
- Any stage can move to any other; the user is in control. Every move is recorded.
- `applied_at` is set the first time the application reaches `applied` or later (the user can edit
  it). `closed_at` is set on `rejected` or `withdrawn` and cleared if reopened.
- Adding an interview to a `saved` or `applied` application moves it to `interviewing` (recorded).

### API
- `GET/POST /api/applications`, `GET/PATCH/DELETE /api/applications/{id}`
- `POST /api/applications/{id}/notes`, `PATCH/DELETE /api/notes/{id}`
- `POST /api/applications/{id}/interviews`, `PATCH/DELETE /api/interviews/{id}`,
  `GET /api/interviews/upcoming`
- `GET /api/analytics`:
  - Stage counts, and a funnel of applications that ever reached each stage.
  - Response, interview and offer rates overall, by source and by match band.
  - Applications per week (12 weeks).
- Jobs gain `application` (id and stage), so lists and job pages show what is already tracked.
- Data export includes all CRM data.

### Frontend
- `/applications`:
  - A Kanban board. Cards move by drag and drop, or by an accessible stage menu on each card.
  - "Track a job applied elsewhere" for jobs not in the app.
- `/applications/[id]`: stage, dates and next action, notes, interviews with checklist and
  outcome, and the timeline.
- Job pages: "Save" or "Track as applied", and the current stage.
- `/analytics`: Recharts charts following the dataviz guidance (one hue for single series, hover
  tooltips, a table view).
- Dashboard: real pipeline counts and upcoming interviews.

## Definition of Done
- [ ] `make check` passes; migrations upgrade and downgrade
- [ ] Tests: stage rules and history, notes, interviews and checklist, upcoming interviews,
      analytics on a known dataset, one application per job, job deletion keeps the application,
      per-user isolation, export, account delete
- [ ] Frontend tests: board stage change, interview form validation, analytics table
- [ ] Running in Docker: save jobs, move them across the board, add notes and an interview, and
      see analytics and dashboard update
- [ ] Docs updated
