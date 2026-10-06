"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { MatchBadge } from "@/components/jobs/match-badge";
import { useJobs } from "@/lib/api/jobs";

export function HighMatchJobs() {
  const jobs = useJobs({ eligibleOnly: true, source: "", q: "", limit: 5, highPriorityOnly: true });
  if (jobs.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const items = jobs.data?.items ?? [];
  if (items.length === 0) {
    return (
      <EmptyState icon={Sparkles} title="No high matches yet">
        Upload your resume, add job sources and run a search. Eligible jobs scoring 85+ appear here.
      </EmptyState>
    );
  }
  return (
    <ul className="grid gap-2">
      {items.map((job) => (
        <li key={job.id} className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <Link
              href={`/jobs/${job.id}`}
              className="block truncate text-sm font-medium hover:underline"
            >
              {job.title}
            </Link>
            <p className="truncate text-xs text-muted-foreground">{job.company}</p>
          </div>
          {job.match && <MatchBadge match={job.match} />}
        </li>
      ))}
      {(jobs.data?.total ?? 0) > items.length && (
        <li>
          <Link href="/jobs" className="text-sm text-primary underline-offset-4 hover:underline">
            See all {jobs.data?.total}
          </Link>
        </li>
      )}
    </ul>
  );
}
