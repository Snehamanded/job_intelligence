import type { JobSummary } from "@/lib/api/client";

const PERIOD: Record<string, string> = { year: "/yr", month: "/mo", hour: "/hr" };

function amount(value: number, currency: string): string {
  if (currency === "INR") {
    if (value >= 10_000_000) return `₹${+(value / 10_000_000).toFixed(2)} Cr`;
    if (value >= 100_000) return `₹${+(value / 100_000).toFixed(1)}L`;
    return `₹${value.toLocaleString("en-IN")}`;
  }
  try {
    return new Intl.NumberFormat("en", {
      style: "currency",
      currency,
      notation: value >= 10_000 ? "compact" : "standard",
      maximumFractionDigits: value >= 10_000 ? 1 : 0,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString()}`;
  }
}

/** Salary as stated by the posting, or null when it isn't listed. Never estimated. */
export function formatSalary(
  job: Pick<
    JobSummary,
    "salary_min" | "salary_max" | "salary_currency" | "salary_period" | "salary_unknown"
  >,
): string | null {
  if (job.salary_unknown || !job.salary_currency) return null;
  const cur = job.salary_currency;
  const period = PERIOD[job.salary_period ?? "year"] ?? "";
  if (job.salary_min != null && job.salary_max != null) {
    return `${amount(job.salary_min, cur)} – ${amount(job.salary_max, cur)}${period}`;
  }
  if (job.salary_max != null) return `Up to ${amount(job.salary_max, cur)}${period}`;
  if (job.salary_min != null) return `From ${amount(job.salary_min, cur)}${period}`;
  return null;
}

export function formatExperience(
  job: Pick<JobSummary, "experience_min_years" | "experience_max_years">,
): string | null {
  const { experience_min_years: min, experience_max_years: max } = job;
  if (min == null) return null;
  return max != null ? `${min}–${max} yrs` : `${min}+ yrs`;
}

export function formatPosted(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) return null;
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : `${months} months ago`;
}

export const EMPLOYMENT_LABEL: Record<string, string> = {
  full_time: "Full-time",
  contract: "Contract",
  internship: "Internship",
  part_time: "Part-time",
};

export const SOURCE_LABEL: Record<string, string> = {
  greenhouse: "Greenhouse",
  manual: "Imported",
  linkedin: "LinkedIn",
  naukri: "Naukri",
  indeed: "Indeed",
};
