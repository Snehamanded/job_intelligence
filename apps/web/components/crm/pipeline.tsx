"use client";

import { CalendarClock, KanbanSquare } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { useAnalytics, useUpcomingInterviews } from "@/lib/api/crm";
import { KIND_LABEL, STAGES, formatDateTime } from "@/lib/crm";

export function Pipeline() {
  const analytics = useAnalytics();
  const upcoming = useUpcomingInterviews();
  const counts = analytics.data?.stage_counts;
  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="grid gap-4">
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-6">
        {STAGES.map((s) => (
          <li key={s.value}>
            <Link
              href="/applications"
              className="block rounded-lg border bg-muted/40 p-3 transition-colors hover:bg-accent"
            >
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="mt-1 text-xl font-semibold">{counts ? (counts[s.value] ?? 0) : "—"}</p>
            </Link>
          </li>
        ))}
      </ul>
      {counts && total === 0 && (
        <EmptyState icon={KanbanSquare} title="No applications tracked yet">
          Save jobs or add applications to see them move through your pipeline.
        </EmptyState>
      )}
      {(upcoming.data ?? []).length > 0 && (
        <div className="grid gap-2">
          <h3 className="text-sm font-semibold">Upcoming interviews</h3>
          <ul className="grid gap-1 text-sm">
            {upcoming.data!.slice(0, 5).map((iv) => (
              <li key={iv.id} className="flex flex-wrap items-center gap-2">
                <CalendarClock className="size-4 text-primary" aria-hidden />
                <span className="font-medium">{formatDateTime(iv.scheduled_at)}</span>
                <Link href={`/applications/${iv.application_id}`} className="hover:underline">
                  {KIND_LABEL[iv.kind]} · {iv.title} at {iv.company}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
