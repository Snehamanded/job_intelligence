import { CalendarClock, MessageSquare } from "lucide-react";
import Link from "next/link";

import { MatchBadge } from "@/components/jobs/match-badge";
import type { Application, MatchSummary, Stage } from "@/lib/api/client";
import { STAGES, formatDate, formatDateTime } from "@/lib/crm";

type Props = {
  application: Application;
  onMove: (stage: Stage) => void;
  draggable?: boolean;
};

export function ApplicationCard({ application: a, onMove, draggable = true }: Props) {
  const match =
    a.match_score != null && a.match_label
      ? ({ match_score: a.match_score, label: a.match_label } as MatchSummary)
      : null;
  return (
    <article
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/application-id", a.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      className="grid min-w-0 cursor-grab gap-2 rounded-lg border bg-card p-3 text-sm shadow-xs active:cursor-grabbing"
      aria-label={`${a.title} at ${a.company}`}
    >
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1 basis-32">
          <Link
            href={`/applications/${a.id}`}
            className="font-medium leading-snug break-words hover:underline"
          >
            {a.title}
          </Link>
          <p className="truncate text-xs text-muted-foreground">{a.company}</p>
        </div>
        {match && <MatchBadge match={match} />}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {a.applied_at && <span>Applied {formatDate(a.applied_at)}</span>}
        {a.next_interview_at && (
          <span className="flex items-center gap-1 text-foreground">
            <CalendarClock className="size-3" aria-hidden /> {formatDateTime(a.next_interview_at)}
          </span>
        )}
        {(a.notes_count ?? 0) > 0 && (
          <span className="flex items-center gap-1">
            <MessageSquare className="size-3" aria-hidden /> {a.notes_count}
          </span>
        )}
      </div>
      {a.next_action && (
        <p className="text-xs">
          Next: {a.next_action}
          {a.next_action_date ? ` (${formatDate(a.next_action_date)})` : ""}
        </p>
      )}
      <select
        aria-label={`Move ${a.title} to stage`}
        value={a.stage}
        onChange={(e) => onMove(e.target.value as Stage)}
        className="h-7 rounded-md border bg-background px-1 text-xs"
      >
        {STAGES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </article>
  );
}
