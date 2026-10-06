import { Briefcase, Clock, MapPin, Wallet } from "lucide-react";
import Link from "next/link";

import { EligibilityList } from "@/components/jobs/eligibility-list";
import { MatchBadge } from "@/components/jobs/match-badge";
import { Badge } from "@/components/ui/badge";
import type { JobSummary } from "@/lib/api/client";
import { STAGE_LABEL } from "@/lib/crm";
import {
  EMPLOYMENT_LABEL,
  SOURCE_LABEL,
  formatExperience,
  formatPosted,
  formatSalary,
} from "@/lib/jobs-format";

export function JobCard({ job }: { job: JobSummary }) {
  const salary = formatSalary(job);
  const experience = formatExperience(job);
  const posted = formatPosted(job.posted_at ?? job.first_seen_at);
  const sources = [job.source, ...(job.also_seen_on ?? []).map((s) => s.source)];

  return (
    <article className="grid gap-3 rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold leading-snug">
            <Link href={`/jobs/${job.id}`} className="hover:underline">
              {job.title}
            </Link>
          </h3>
          <p className="text-sm text-muted-foreground">{job.company}</p>
        </div>
        {job.application && <Badge variant="outline">{STAGE_LABEL[job.application.stage]}</Badge>}
        {job.match?.high_priority && <Badge variant="success">High priority</Badge>}
        {job.is_mock && <Badge variant="warning">Mock data</Badge>}
        {!job.eligibility.eligible && <Badge variant="destructive">Not eligible</Badge>}
        {job.match && <MatchBadge match={job.match} />}
      </div>

      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <div className="flex items-center gap-1">
          <MapPin className="size-3.5" aria-hidden />
          <dt className="sr-only">Location</dt>
          <dd>{(job.locations ?? []).join(" · ") || "Location not stated"}</dd>
        </div>
        <div className="flex items-center gap-1">
          <Wallet className="size-3.5" aria-hidden />
          <dt className="sr-only">Salary</dt>
          <dd>{salary ?? "Salary not listed"}</dd>
        </div>
        {experience && (
          <div className="flex items-center gap-1">
            <Briefcase className="size-3.5" aria-hidden />
            <dt className="sr-only">Experience</dt>
            <dd>{experience}</dd>
          </div>
        )}
        {posted && (
          <div className="flex items-center gap-1">
            <Clock className="size-3.5" aria-hidden />
            <dt className="sr-only">Posted</dt>
            <dd>{posted}</dd>
          </div>
        )}
      </dl>

      <div className="flex flex-wrap items-center gap-1.5">
        {job.remote_type === "remote" && <Badge variant="secondary">Remote</Badge>}
        {job.remote_type === "hybrid" && <Badge variant="secondary">Hybrid</Badge>}
        {EMPLOYMENT_LABEL[job.employment_type] && (
          <Badge variant="outline">{EMPLOYMENT_LABEL[job.employment_type]}</Badge>
        )}
        <span className="text-xs text-muted-foreground">
          via {sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ")}
        </span>
      </div>

      <EligibilityList checks={job.eligibility.checks} compact />
    </article>
  );
}
