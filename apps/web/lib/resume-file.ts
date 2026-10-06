export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];

/** Quick client-side check. The server re-validates by content, so this is only for fast feedback. */
export function validateResumeFile(file: { name: string; size: number }): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return "Upload a PDF, DOCX or TXT file.";
  }
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_RESUME_BYTES) return "The file is larger than 5 MB.";
  return null;
}

export function formatMonths(months: number | null | undefined): string {
  if (months == null) return "Unknown";
  const years = Math.floor(months / 12);
  const rest = months % 12;
  const parts = [];
  if (years) parts.push(`${years} yr`);
  if (rest || !years) parts.push(`${rest} mo`);
  return parts.join(" ");
}
