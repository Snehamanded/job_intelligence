import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LetterPreview } from "@/components/cover-letters/letter-preview";
import { SentenceEditor } from "@/components/cover-letters/sentence-editor";
import type { LetterParagraph } from "@/lib/api/client";

const paragraphs: LetterParagraph[] = [
  {
    id: "p0",
    sentences: [
      {
        id: "a0-1",
        text: "Your team builds REST APIs with FastAPI.",
        kind: "company",
        job_quote: "build REST APIs",
        sources: [],
        source: "ai",
        status: "proposed",
        issues: [],
        included: true,
      },
      {
        id: "a0-2",
        text: "Acme was founded in 1999.",
        kind: "company",
        job_quote: "founded in 1999",
        sources: [],
        source: "ai",
        status: "unsupported",
        issues: ["The quoted text isn't in the job posting"],
        included: false,
      },
      {
        id: "u1",
        text: "I can start in November.",
        kind: "claim",
        sources: [],
        source: "user",
        status: "proposed",
        issues: [],
        included: true,
      },
    ],
  },
];

describe("SentenceEditor", () => {
  it("labels sentences, shows quotes and problems, and blocks unsupported ones", () => {
    render(<SentenceEditor paragraphs={paragraphs} onEdit={vi.fn()} />);
    expect(screen.getAllByText("AI · About the company", { selector: "span" })).toHaveLength(2);
    expect(screen.getByText("From the posting: “build REST APIs”")).toBeInTheDocument();
    expect(screen.getByText("Your words")).toBeInTheDocument();
    const bad = screen.getByLabelText("Include: Acme was founded in 1999.");
    expect(bad).toBeDisabled();
    expect(bad).not.toBeChecked();
    expect(screen.getByText("The quoted text isn't in the job posting")).toBeInTheDocument();
  });

  it("sends include toggles, edits and new sentences", async () => {
    const onEdit = vi.fn();
    render(<SentenceEditor paragraphs={paragraphs} onEdit={onEdit} />);
    await userEvent.click(
      screen.getByLabelText("Include: Your team builds REST APIs with FastAPI."),
    );
    expect(onEdit).toHaveBeenLastCalledWith({ updates: { "a0-1": { included: false } } });

    await userEvent.click(screen.getByRole("button", { name: "Edit: Acme was founded in 1999." }));
    const box = screen.getByLabelText("Sentence text");
    await userEvent.clear(box);
    await userEvent.type(box, "I admire Acme's payments work.");
    await userEvent.click(screen.getByRole("button", { name: "Use my wording" }));
    expect(onEdit).toHaveBeenLastCalledWith({
      updates: { "a0-2": { text: "I admire Acme's payments work." } },
    });

    await userEvent.type(
      screen.getByLabelText("Add your own sentence to paragraph 1"),
      "I am based in Pune.",
    );
    await userEvent.click(
      within(screen.getByRole("region", { name: "Paragraph 1" })).getByRole("button", {
        name: "Add",
      }),
    );
    expect(onEdit).toHaveBeenLastCalledWith({
      add: [{ paragraph_id: "p0", text: "I am based in Pune." }],
    });
  });

  it("is read-only once saved", () => {
    render(<SentenceEditor paragraphs={paragraphs} onEdit={vi.fn()} readOnly />);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit/ })).toBeNull();
  });
});

describe("LetterPreview", () => {
  it("adds the greeting and signature around the paragraphs", () => {
    render(
      <LetterPreview company="Acme" paragraphs={["First.", "Second."]} signature="Sneha Rao" />,
    );
    const letter = screen.getByRole("article", { name: "Letter preview" });
    expect(letter).toHaveTextContent(
      /^Dear Hiring Team at Acme,First\.Second\.Sincerely,Sneha Rao$/,
    );
  });
});
