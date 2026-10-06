import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Board } from "@/components/crm/board";
import { RatesTable } from "@/components/crm/charts";
import { ExternalApplicationForm } from "@/components/crm/external-form";
import { InterviewForm } from "@/components/crm/interview-form";
import { Timeline } from "@/components/crm/timeline";
import type { Application, ApplicationDetail } from "@/lib/api/client";

const base: Application = {
  id: "a1",
  job_id: "j1",
  title: "Backend Engineer",
  company: "Acme",
  location: "Bengaluru, India",
  url: null,
  source: "greenhouse",
  match_score: 74,
  match_label: "Good",
  stage: "saved",
  position: 0,
  applied_at: null,
  closed_at: null,
  next_action: "Ask for a referral",
  next_action_date: null,
  created_at: "2026-10-06T00:00:00Z",
  updated_at: "2026-10-06T00:00:00Z",
  next_interview_at: null,
  notes_count: 2,
};

describe("Board", () => {
  it("places cards in their stage column and moves them via the stage menu", async () => {
    const onMove = vi.fn();
    render(
      <Board
        applications={[
          base,
          { ...base, id: "a2", title: "Data Analyst", stage: "applied", applied_at: "2026-10-01" },
        ]}
        onMove={onMove}
      />,
    );
    const saved = within(screen.getByRole("region", { name: "Saved" }));
    expect(saved.getByText("Backend Engineer")).toBeInTheDocument();
    expect(saved.getByText("Next: Ask for a referral")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Applied" })).getByText("Data Analyst"),
    ).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Move Backend Engineer to stage"),
      "interviewing",
    );
    expect(onMove).toHaveBeenCalledWith("a1", "interviewing");
  });
});

describe("InterviewForm", () => {
  it("requires a date and sends a timezone-aware time and checklist", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<InterviewForm onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Add interview" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose the interview date and time.");
    expect(onSubmit).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Date and time"), "2026-10-20T15:30");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "technical");
    await userEvent.type(
      screen.getByLabelText(/Preparation checklist/),
      "Review SQL{enter}{enter}Mock interview",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add interview" }));
    const sent = onSubmit.mock.calls[0][0];
    expect(sent.kind).toBe("technical");
    expect(sent.scheduled_at).toMatch(/Z$/);
    expect(new Date(sent.scheduled_at).getTime()).toBe(new Date("2026-10-20T15:30").getTime());
    expect(sent.checklist).toEqual([
      { text: "Review SQL", done: false },
      { text: "Mock interview", done: false },
    ]);
  });
});

describe("ExternalApplicationForm", () => {
  it("validates title, company and link", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ExternalApplicationForm onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Add to board" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the job title and company.");
    await userEvent.type(screen.getByLabelText("Job title"), "Data Engineer");
    await userEvent.type(screen.getByLabelText("Company"), "Elsewhere");
    await userEvent.type(screen.getByLabelText("Link (optional)"), "ftp://x");
    await userEvent.click(screen.getByRole("button", { name: "Add to board" }));
    expect(screen.getByRole("alert")).toHaveTextContent("must start with http");
    await userEvent.clear(screen.getByLabelText("Link (optional)"));
    await userEvent.click(screen.getByRole("button", { name: "Add to board" }));
    expect(onSubmit).toHaveBeenCalledWith({
      title: "Data Engineer",
      company: "Elsewhere",
      stage: "applied",
    });
  });
});

describe("RatesTable", () => {
  it("shows counts and rates as text, with meters", () => {
    render(
      <RatesTable
        caption="Rates by source"
        rows={[
          {
            group: "greenhouse",
            applied: 4,
            responded: 3,
            interviews: 2,
            offers: 1,
            response_rate: 0.75,
            interview_rate: 0.5,
            offer_rate: 0.25,
          },
          {
            group: "external",
            applied: 0,
            responded: 0,
            interviews: 0,
            offers: 0,
            response_rate: null,
            interview_rate: null,
            offer_rate: null,
          },
        ]}
      />,
    );
    const row = within(screen.getByRole("row", { name: /greenhouse/ }));
    expect(row.getByText("75%")).toBeInTheDocument();
    expect(row.getByText("50%")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /external/ })).getAllByText("—")).toHaveLength(3);
  });
});

describe("Timeline", () => {
  it("describes the history newest first", () => {
    const events: ApplicationDetail["events"] = [
      {
        id: "e1",
        kind: "created",
        from_stage: null,
        to_stage: "saved",
        detail: null,
        created_at: "2026-10-01T00:00:00Z",
      },
      {
        id: "e2",
        kind: "stage_changed",
        from_stage: "applied",
        to_stage: "interviewing",
        detail: "Interview scheduled",
        created_at: "2026-10-02T00:00:00Z",
      },
    ];
    render(<Timeline events={events} />);
    const items = within(screen.getByRole("list", { name: "History" })).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Applied → Interviewing (Interview scheduled)");
    expect(items[1]).toHaveTextContent("Added as Saved");
  });
});
