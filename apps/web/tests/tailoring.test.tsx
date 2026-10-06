import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChangeList } from "@/components/tailoring/change-list";
import { ResumePreview } from "@/components/tailoring/resume-preview";
import type { Change, ResumeDocument } from "@/lib/api/client";

const changes: Change[] = [
  {
    id: "ai-rewrite-r0b0",
    kind: "bullet_rewrite",
    source: "ai",
    status: "proposed",
    decision: "pending",
    title: "Reword a bullet: Software Engineer",
    reason: "Stronger verb",
    issues: [],
    before: "Built REST APIs in FastAPI",
    after: "Designed and built REST APIs with FastAPI",
  },
  {
    id: "ai-rewrite-r0b1",
    kind: "bullet_rewrite",
    source: "ai",
    status: "unsupported",
    decision: "pending",
    title: "Reword a bullet: metrics",
    issues: ["Adds the number “60”, which the original bullet doesn't have"],
    before: "Reduced report time by 40%",
    after: "Cut report time by 60%",
  },
  {
    id: "rules-skills",
    kind: "skills_order",
    source: "rules",
    status: "proposed",
    decision: "accepted",
    title: "Put the skills this job asks for first",
    issues: [],
    labels: ["PostgreSQL", "Python", "FastAPI"],
  },
];

describe("ChangeList", () => {
  it("labels every change and blocks accepting unsupported ones", async () => {
    const onDecide = vi.fn();
    render(<ChangeList changes={changes} onDecide={onDecide} />);

    const good = within(
      screen.getByRole("listitem", { name: "Reword a bullet: Software Engineer" }),
    );
    expect(good.getByText("AI suggestion")).toBeInTheDocument();
    expect(good.getByText("Built REST APIs in FastAPI")).toBeInTheDocument();
    await userEvent.click(good.getByRole("button", { name: "Accept" }));
    expect(onDecide).toHaveBeenCalledWith("ai-rewrite-r0b0", "accepted");

    const bad = within(screen.getByRole("listitem", { name: "Reword a bullet: metrics" }));
    expect(bad.getByText("Unsupported")).toBeInTheDocument();
    expect(bad.getByText(/Adds the number “60”/)).toBeInTheDocument();
    expect(bad.getByRole("button", { name: "Accept" })).toBeDisabled();

    const rules = within(
      screen.getByRole("listitem", { name: "Put the skills this job asks for first" }),
    );
    expect(rules.getByText("Rule-based")).toBeInTheDocument();
    expect(rules.getByRole("button", { name: "Accept" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(rules.getByRole("button", { name: "Accept" }));
    expect(onDecide).toHaveBeenLastCalledWith("rules-skills", "pending");
  });

  it("is read-only once saved", () => {
    render(<ChangeList changes={changes} onDecide={vi.fn()} readOnly />);
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });
});

describe("ResumePreview", () => {
  const doc: ResumeDocument = {
    contact: { name: "Sneha Rao", email: "sneha.rao@example.com", links: [] },
    summary: [{ text: "Python backend developer.", sources: ["s0"] }],
    skills: [{ id: "s0", name: "Python" }],
    experience: [
      {
        id: "r0",
        title: "Software Engineer",
        company: "Acme",
        date_text: "Jul 2025 - Present",
        bullets: [
          {
            id: "r0b0",
            text: "Designed and built REST APIs",
            original_text: "Built REST APIs",
            source_span: null,
            ai_changed: true,
          },
          {
            id: "r0b1",
            text: "Tuned queries",
            original_text: "Tuned queries",
            source_span: null,
            ai_changed: false,
          },
        ],
      },
    ],
    projects: [],
    education: [],
    certifications: [],
  };

  it("renders a plain resume and only highlights AI rewording in the editor", () => {
    const { rerender } = render(<ResumePreview doc={doc} highlight />);
    expect(screen.getByRole("heading", { name: "Sneha Rao" })).toBeInTheDocument();
    expect(screen.getByText("Designed and built REST APIs")).toHaveAttribute(
      "title",
      "AI-reworded. Original: Built REST APIs",
    );
    expect(screen.getByText("Tuned queries")).not.toHaveAttribute("title");
    rerender(<ResumePreview doc={doc} />);
    expect(screen.getByText("Designed and built REST APIs")).not.toHaveAttribute("title");
  });
});
