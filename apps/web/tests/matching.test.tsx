import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MatchBreakdown } from "@/components/jobs/match-breakdown";
import { PriorityControl } from "@/components/jobs/priority-control";
import { ScoringForm } from "@/components/jobs/scoring-form";
import { SkillsList } from "@/components/jobs/skills-list";
import type { MatchDetail, ScoringSettings } from "@/lib/api/client";

const components: MatchDetail["components"] = {
  skills: {
    score: 83,
    weight: 30,
    method: "ai",
    detail: "Skills in the posting vs your profile, reviewed by AI",
  },
  experience: {
    score: 100,
    weight: 20,
    method: "code",
    detail: "Needs 1+ years; you have about 1.8",
  },
  location: { score: 0, weight: 10, method: "code", detail: "Remote only in United States" },
  industry: {
    score: 50,
    weight: 5,
    method: "unknown",
    detail: "Industry fit is assessed only with AI processing on",
  },
};

describe("MatchBreakdown", () => {
  it("renders one labelled meter per component, in a fixed order, with visible details", () => {
    render(<MatchBreakdown components={components} />);
    const meters = screen.getAllByRole("meter");
    expect(meters.map((m) => m.getAttribute("aria-label"))).toEqual([
      "Skills score",
      "Experience score",
      "Location score",
      "Industry score",
    ]);
    expect(meters[0]).toHaveAttribute("aria-valuenow", "83");
    expect(screen.getByText("Remote only in United States")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });
});

describe("SkillsList", () => {
  it("groups skills and never shows related as on your resume", () => {
    render(
      <SkillsList
        skills={[
          { name: "Python", status: "demonstrated", profile_skills: ["Python"] },
          { name: "Kubernetes", status: "related", profile_skills: ["Docker"] },
          { name: "Go", status: "not_demonstrated", profile_skills: [] },
        ]}
      />,
    );
    const onResume = within(screen.getByRole("region", { name: "On your resume" }));
    expect(onResume.getByText("Python")).toBeInTheDocument();
    expect(onResume.queryByText(/Kubernetes/)).toBeNull();
    const related = within(screen.getByRole("region", { name: "Related experience" }));
    expect(related.getByText(/via Docker/)).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Not on your resume" })).getByText("Go"),
    ).toBeInTheDocument();
  });
});

describe("PriorityControl", () => {
  it("reports the chosen priority", async () => {
    const onChange = vi.fn();
    render(<PriorityControl value={1} onChange={onChange} />);
    expect(screen.getByRole("radio", { name: "Normal" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: "High" }));
    expect(onChange).toHaveBeenCalledWith(2);
  });
});

describe("ScoringForm", () => {
  const initial: ScoringSettings = {
    weights: {
      skills: 30,
      experience: 20,
      role: 20,
      location: 10,
      projects: 10,
      industry: 5,
      preferences: 5,
    },
    ranking: { match: 0.7, freshness: 0.1, salary_fit: 0.1, user_priority: 0.1 },
    bands: { excellent: 90, strong: 80, good: 70, moderate: 60 },
    high_priority_threshold: 85,
    llm_top_n: 10,
  };

  it("requires ranking percentages to total 100", async () => {
    const onSubmit = vi.fn();
    render(<ScoringForm initial={initial} onSubmit={onSubmit} />);
    const match = screen.getByLabelText("Match score");
    await userEvent.clear(match);
    await userEvent.type(match, "80");
    await userEvent.click(screen.getByRole("button", { name: "Save and rescore" }));
    expect(screen.getByRole("alert")).toHaveTextContent("must add up to 100 (now 110)");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits weights and ranking as fractions", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ScoringForm initial={initial} onSubmit={onSubmit} />);
    const skills = screen.getByLabelText("skills");
    await userEvent.clear(skills);
    await userEvent.type(skills, "50");
    await userEvent.click(screen.getByRole("button", { name: "Save and rescore" }));
    const sent = onSubmit.mock.calls[0][0] as ScoringSettings;
    expect(sent.weights?.skills).toBe(50);
    expect(sent.ranking).toEqual({
      match: 0.7,
      freshness: 0.1,
      salary_fit: 0.1,
      user_priority: 0.1,
    });
    expect(sent.llm_top_n).toBe(10);
  });
});
