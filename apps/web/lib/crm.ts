import type { Stage } from "@/lib/api/client";

export const STAGES: { value: Stage; label: string }[] = [
  { value: "saved", label: "Saved" },
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

export const STAGE_LABEL = Object.fromEntries(STAGES.map((s) => [s.value, s.label])) as Record<
  Stage,
  string
>;

export const INTERVIEW_KINDS = [
  { value: "phone_screen", label: "Phone screen" },
  { value: "technical", label: "Technical" },
  { value: "system_design", label: "System design" },
  { value: "behavioral", label: "Behavioral" },
  { value: "hiring_manager", label: "Hiring manager" },
  { value: "onsite", label: "Onsite" },
  { value: "other", label: "Other" },
] as const;

export const KIND_LABEL: Record<string, string> = Object.fromEntries(
  INTERVIEW_KINDS.map((k) => [k.value, k.label]),
);

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function percent(rate: number | null | undefined): string {
  return rate == null ? "—" : `${Math.round(rate * 100)}%`;
}
