import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProfileReview } from "@/components/profile/profile-review";
import type { Profile } from "@/lib/api/client";

const span = { start: 0, end: 6 };

const profile: Profile = {
  id: "p1",
  version: 2,
  origin: "parsed",
  parse_method: "llm",
  resume_id: "r1",
  experience_months: 22,
  created_at: "2026-10-05T00:00:00Z",
  preferences: {
    target_roles: [],
    remote_scope: "none",
    onsite_locations: [],
    open_to: ["full_time"],
    min_salary: null,
    currency: null,
    salary_unknown_policy: "include",
  },
  data: {
    contact: { name: "Sneha Rao", email: "sneha.rao@example.com", links: [] },
    skills: [
      { name: "Python", source: "resume", evidence: "Languages: Python, SQL", source_span: span },
      { name: "SQL", source: "resume", evidence: "Languages: Python, SQL", source_span: span },
    ],
    experience: [
      {
        title: "Software Engineer",
        company: "Acme Analytics",
        date_text: "Jul 2025 - Present",
        is_current: true,
        source: "resume",
        evidence: "Software Engineer | Acme Analytics | Jul 2025 - Present",
        source_span: span,
        bullets: [{ text: "Built REST APIs in FastAPI", source: "resume", source_span: span }],
      },
    ],
    projects: [],
    education: [],
    certifications: [],
    unsupported: [
      {
        kind: "skill",
        label: "Kubernetes",
        evidence: "Deployed on Kubernetes",
        reason: "Quoted text was not found in the resume",
      },
    ],
  },
};

describe("ProfileReview", () => {
  it("shows provenance, experience and the excluded claims", () => {
    render(<ProfileReview profile={profile} onSave={vi.fn()} />);
    expect(screen.getByText("Parsed with AI")).toBeInTheDocument();
    expect(screen.getByText("1 yr 10 mo")).toBeInTheDocument();
    expect(screen.getAllByLabelText("From your resume: Languages: Python, SQL")).toHaveLength(2);
    const excluded = screen.getByRole("region", { name: /Not saved/ });
    expect(within(excluded).getByText("Kubernetes")).toBeInTheDocument();
    // Excluded claims are not shown as skills.
    expect(
      within(screen.getByRole("list", { name: "Skills" })).queryByText("Kubernetes"),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /Save as version/ })).not.toBeInTheDocument();
  });

  it("removes and adds items, labels user additions, and saves the edited data", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ProfileReview profile={profile} onSave={onSave} />);

    await userEvent.click(screen.getByRole("button", { name: "Remove SQL" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Remove Built REST APIs in FastAPI" }),
    );
    await userEvent.type(screen.getByLabelText("New skill"), "Kubernetes");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    const skills = screen.getByRole("list", { name: "Skills" });
    expect(within(skills).getByText("Added by you")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Save as version 3" }));
    const saved = onSave.mock.calls[0][0];
    expect(saved.skills.map((s: { name: string }) => s.name)).toEqual(["Python", "Kubernetes"]);
    expect(saved.skills[1]).toEqual({ name: "Kubernetes", source: "user" });
    expect(saved.experience[0].bullets).toEqual([]);
  });

  it("does not add duplicate skills and can discard changes", async () => {
    render(<ProfileReview profile={profile} onSave={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("New skill"), "python");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.queryByRole("button", { name: /Save as version/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Remove Python" }));
    await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.getByRole("button", { name: "Remove Python" })).toBeInTheDocument();
  });
});
