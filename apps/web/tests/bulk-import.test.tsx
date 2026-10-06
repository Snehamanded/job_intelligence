import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ImportBatch } from "@/lib/api/client";

const post = vi.fn();
const get = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      POST: (...args: unknown[]) => post(...args),
      GET: (...args: unknown[]) => get(...args),
    },
  };
});

import { BulkImportForm } from "@/components/jobs/bulk-import-form";

const done: ImportBatch = {
  id: "b1",
  channel: "whatsapp",
  status: "completed",
  method: "rules",
  notice: "AI processing is off. Turn it on in Settings for better results.",
  error_message: null,
  created_at: "2026-10-06T00:00:00Z",
  finished_at: "2026-10-06T00:00:05Z",
  results: [
    {
      title: "Python Developer",
      company: "Acme Cloudworks",
      url: null,
      job_id: "j1",
      status: "new",
      note: null,
    },
    {
      title: "Data Analyst Intern",
      company: "Zentrix Analytics",
      url: null,
      job_id: "j2",
      status: "duplicate",
      note: "Only a short summary was in the message.",
    },
  ],
};

describe("BulkImportForm", () => {
  it("sends the pasted posts with their channel and lists what was found", async () => {
    post.mockResolvedValue({ data: { ...done, status: "queued", results: [] }, response: {} });
    get.mockResolvedValue({ data: done, response: {} });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <BulkImportForm />
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "WhatsApp" }));
    expect(screen.getByText(/Names and phone numbers are removed/)).toBeInTheDocument();
    await user.type(
      screen.getByLabelText("Pasted posts"),
      "Hiring Python Developer at Acme Cloudworks, apply now",
    );
    await user.click(screen.getByRole("button", { name: "Find and import jobs" }));

    expect(post).toHaveBeenCalledWith("/api/job-imports", {
      body: { channel: "whatsapp", text: "Hiring Python Developer at Acme Cloudworks, apply now" },
    });
    expect(await screen.findByText("Found 2 job posts; 2 in your jobs.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Python Developer" })).toHaveAttribute(
      "href",
      "/jobs/j1",
    );
    expect(screen.getByText("Already added")).toBeInTheDocument();
    expect(screen.getByText(/AI processing is off/)).toBeInTheDocument();
  });

  it("asks for text before importing", async () => {
    post.mockReset();
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <BulkImportForm />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Find and import jobs" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Paste the job posts first.");
    expect(post).not.toHaveBeenCalled();
  });
});
