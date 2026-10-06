import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SearchRun } from "@/lib/api/client";

const STATUS_VARIANT = {
  completed: "success",
  partial: "warning",
  failed: "destructive",
  skipped: "secondary",
} as const;

export function SearchStatus({ run }: { run: SearchRun }) {
  const running = run.status === "queued" || run.status === "running";
  return (
    <div className="grid gap-2 text-sm" aria-live="polite">
      <p className="flex flex-wrap items-center gap-2">
        {running ? (
          <>
            <Loader2 className="size-4 animate-spin" /> Searching…
          </>
        ) : (
          <>
            Last search {run.finished_at ? new Date(run.finished_at).toLocaleString() : ""}
            {run.keywords.length > 0 && (
              <span className="text-muted-foreground">for “{run.keywords.join("”, “")}”</span>
            )}
          </>
        )}
      </p>
      {run.error_message && <p className="text-amber-700">{run.error_message}</p>}
      <ul className="grid gap-1" aria-label="Sources">
        {run.source_results.map((r) => (
          <li key={r.source} className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{r.label}</span>
            <Badge variant={STATUS_VARIANT[r.status]}>{r.status}</Badge>
            {r.is_mock && <Badge variant="warning">mock</Badge>}
            {r.status !== "skipped" && r.status !== "failed" && (
              <span className="text-muted-foreground">
                {r.fetched} fetched · {r.kept} matched · {r.new} new
                {(r.duplicates ?? 0) > 0 ? ` · ${r.duplicates} duplicates merged` : ""}
              </span>
            )}
            {r.error && <span className="text-xs text-muted-foreground">({r.error})</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
