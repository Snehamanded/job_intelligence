import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UploadCard } from "@/components/resume/upload-card";
import { formatMonths, validateResumeFile } from "@/lib/resume-file";

const file = (name: string, size: number) =>
  new File([new Uint8Array(size)], name, { type: "application/octet-stream" });

describe("UploadCard", () => {
  it("rejects unsupported types and oversize files without uploading", async () => {
    const onUpload = vi.fn();
    render(<UploadCard onUpload={onUpload} />);
    const input = screen.getByLabelText("Resume file");

    await userEvent.upload(input, file("resume.doc", 100), { applyAccept: false });
    expect(screen.getByRole("alert")).toHaveTextContent("Upload a PDF, DOCX or TXT file.");

    await userEvent.upload(input, file("resume.pdf", 5 * 1024 * 1024 + 1));
    expect(screen.getByRole("alert")).toHaveTextContent("larger than 5 MB");
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("uploads a valid file", async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    render(<UploadCard onUpload={onUpload} />);
    const pdf = file("Sneha CV.PDF", 2048);
    await userEvent.upload(screen.getByLabelText("Resume file"), pdf);
    expect(onUpload).toHaveBeenCalledWith(pdf);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows server errors", () => {
    render(<UploadCard onUpload={vi.fn()} serverError="The file content is not a valid PDF" />);
    expect(screen.getByRole("alert")).toHaveTextContent("not a valid PDF");
  });
});

describe("resume file helpers", () => {
  it("validates", () => {
    expect(validateResumeFile({ name: "a.txt", size: 0 })).toBe("The file is empty.");
    expect(validateResumeFile({ name: "a.docx", size: 10 })).toBeNull();
  });

  it.each([
    [null, "Unknown"],
    [0, "0 mo"],
    [7, "7 mo"],
    [12, "1 yr"],
    [22, "1 yr 10 mo"],
  ])("formatMonths(%s) = %s", (months, expected) => {
    expect(formatMonths(months)).toBe(expected);
  });
});
