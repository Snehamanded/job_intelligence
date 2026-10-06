import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ImportForm } from "@/components/jobs/import-form";
import { JobCard } from "@/components/jobs/job-card";
import { SearchStatus } from "@/components/jobs/search-status";
import type { JobSummary, SearchRun } from "@/lib/api/client";
import { formatExperience, formatPosted, formatSalary } from "@/lib/jobs-format";

const job: JobSummary = {
  id: "j1",
  source: "greenhouse",
  title: "Backend Engineer",
  company: "Acme",
  url: "https://job-boards.greenhouse.io/acme/jobs/1",
  locations: ["Remote (United States)"],
  remote_type: "remote",
  remote_regions: ["United States"],
  employment_type: "full_time",
  salary_min: 139200,
  salary_max: 235200,
  salary_currency: "USD",
  salary_period: "year",
  salary_text: "$139,200 — $235,200 USD",
  salary_unknown: false,
  experience_min_years: 3,
  experience_max_years: null,
  posted_at: "2026-10-01T00:00:00Z",
  first_seen_at: "2026-10-05T00:00:00Z",
  is_mock: false,
  priority: 1,
  match: {
    match_score: 72,
    rank_score: 68.4,
    label: "Good",
    high_priority: false,
    method: "lexical",
  },
  also_seen_on: [{ source: "naukri", source_job_id: "x" }],
  eligibility: {
    eligible: false,
    checks: [
      { name: "employment_type", status: "pass", reason: "Full-time, which you're open to" },
      { name: "location", status: "fail", reason: "Remote only in United States" },
      { name: "salary", status: "unknown", reason: "Salary is in USD, not INR; not compared" },
      { name: "experience", status: "pass", reason: "Needs 3+ years; you have about 2.5" },
    ],
  },
};

describe("job formatting", () => {
  it("formats salaries without inventing any", () => {
    expect(formatSalary(job)).toBe("$139.2K – $235.2K/yr");
    expect(
      formatSalary({ ...job, salary_currency: "INR", salary_min: 1200000, salary_max: 1800000 }),
    ).toBe("₹12L – ₹18L/yr");
    expect(
      formatSalary({
        ...job,
        salary_currency: "INR",
        salary_min: 25000,
        salary_max: null,
        salary_period: "month",
      }),
    ).toBe("From ₹25,000/mo");
    expect(
      formatSalary({ ...job, salary_min: null, salary_max: 1500000, salary_currency: "INR" }),
    ).toBe("Up to ₹15L/yr");
    expect(formatSalary({ ...job, salary_unknown: true })).toBeNull();
  });

  it("formats experience and freshness", () => {
    expect(formatExperience(job)).toBe("3+ yrs");
    expect(formatExperience({ experience_min_years: 1, experience_max_years: 3 })).toBe("1–3 yrs");
    expect(formatExperience({ experience_min_years: null, experience_max_years: null })).toBeNull();
    const now = new Date("2026-10-06T12:00:00Z");
    expect(formatPosted("2026-10-06T08:00:00Z", now)).toBe("Today");
    expect(formatPosted("2026-10-01T00:00:00Z", now)).toBe("5 days ago");
    expect(formatPosted("2026-07-01T00:00:00Z", now)).toBe("3 months ago");
  });
});

describe("JobCard", () => {
  it("shows facts, sources and only the non-passing eligibility reasons", () => {
    render(<JobCard job={job} />);
    expect(screen.getByRole("link", { name: "Backend Engineer" })).toHaveAttribute(
      "href",
      "/jobs/j1",
    );
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("$139.2K – $235.2K/yr")).toBeInTheDocument();
    expect(screen.getByText("via Greenhouse, Naukri")).toBeInTheDocument();
    expect(screen.getByLabelText("Match 72 out of 100, Good")).toBeInTheDocument();
    const reasons = within(screen.getByRole("list", { name: "Eligibility" }));
    expect(reasons.getByText("Remote only in United States")).toBeInTheDocument();
    expect(reasons.getByText(/not compared/)).toBeInTheDocument();
    expect(reasons.queryByText(/open to/)).toBeNull();
  });

  it("says when salary is not listed and labels mock data", () => {
    render(<JobCard job={{ ...job, salary_unknown: true, is_mock: true }} />);
    expect(screen.getByText("Salary not listed")).toBeInTheDocument();
    expect(screen.getByText("Mock data")).toBeInTheDocument();
  });
});

describe("SearchStatus", () => {
  it("shows per-source results including failures", () => {
    const run: SearchRun = {
      id: "r1",
      status: "completed",
      keywords: ["Backend Engineer"],
      error_message: null,
      created_at: "2026-10-06T00:00:00Z",
      started_at: "2026-10-06T00:00:00Z",
      finished_at: "2026-10-06T00:00:05Z",
      source_results: [
        {
          source: "greenhouse",
          label: "Greenhouse",
          status: "partial",
          fetched: 120,
          kept: 8,
          new: 5,
          updated: 2,
          duplicates: 1,
          is_mock: false,
          error: "acme: Board not found",
        },
        {
          source: "broken",
          label: "Broken",
          status: "failed",
          error: "Source is down",
          fetched: 0,
          kept: 0,
          new: 0,
          updated: 0,
          duplicates: 0,
          is_mock: false,
        },
      ],
    };
    render(<SearchStatus run={run} />);
    expect(
      screen.getByText(/120 fetched · 8 matched · 5 new · 1 duplicates merged/),
    ).toBeInTheDocument();
    expect(screen.getByText("(acme: Board not found)")).toBeInTheDocument();
    expect(screen.getByText("(Source is down)")).toBeInTheDocument();
  });
});

describe("ImportForm", () => {
  it("validates a Greenhouse link before importing", async () => {
    const onImport = vi.fn().mockResolvedValue(undefined);
    render(<ImportForm onImport={onImport} />);
    await userEvent.type(screen.getByLabelText("Job link"), "https://www.linkedin.com/jobs/view/1");
    await userEvent.click(screen.getByRole("button", { name: "Import job" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Paste a Greenhouse job link");
    expect(onImport).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText("Job link"));
    await userEvent.type(
      screen.getByLabelText("Job link"),
      "https://job-boards.greenhouse.io/acme/jobs/42",
    );
    await userEvent.click(screen.getByRole("button", { name: "Import job" }));
    expect(onImport).toHaveBeenCalledWith({ url: "https://job-boards.greenhouse.io/acme/jobs/42" });
  });

  it("requires title, company and a real description when pasting", async () => {
    const onImport = vi.fn().mockResolvedValue(undefined);
    render(<ImportForm onImport={onImport} />);
    await userEvent.click(screen.getByRole("tab", { name: "Paste description" }));
    await userEvent.type(screen.getByLabelText("Job title"), "Python Developer");
    await userEvent.click(screen.getByRole("button", { name: "Import job" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Title and company are required.");

    await userEvent.type(screen.getByLabelText("Company"), "Example Corp");
    await userEvent.type(screen.getByLabelText("Job description"), "Too short");
    await userEvent.click(screen.getByRole("button", { name: "Import job" }));
    expect(screen.getByRole("alert")).toHaveTextContent("at least 50 characters");

    await userEvent.type(
      screen.getByLabelText("Job description"),
      " — we need someone with 2+ years of Python experience. CTC 10-14 LPA.",
    );
    await userEvent.type(screen.getByLabelText("Location"), "Bengaluru");
    await userEvent.click(screen.getByRole("button", { name: "Import job" }));
    expect(onImport).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Python Developer",
        company: "Example Corp",
        location: "Bengaluru",
      }),
    );
  });
});
