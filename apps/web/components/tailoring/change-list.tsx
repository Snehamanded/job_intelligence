"use client";

import { AlertTriangle, Check, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Change } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Props = {
  changes: Change[];
  onDecide: (id: string, decision: "accepted" | "rejected" | "pending") => void;
  readOnly?: boolean;
  busy?: boolean;
};

function Detail({ change }: { change: Change }) {
  if (change.kind === "bullet_rewrite") {
    return (
      <div className="grid gap-1 text-sm">
        <p className="text-muted-foreground line-through decoration-muted-foreground/60">
          {change.before}
        </p>
        <p>{change.after}</p>
      </div>
    );
  }
  if (change.kind === "summary") {
    return (
      <ul className="grid gap-1 text-sm">
        {(change.sentences ?? []).map((s, i) => (
          <li key={i}>
            {s.text}{" "}
            <span className="text-xs text-muted-foreground">(cites {s.sources?.join(", ")})</span>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ol className="list-inside list-decimal text-sm text-muted-foreground">
      {(change.labels ?? []).slice(0, 8).map((label, i) => (
        <li key={i} className="truncate">
          {label}
        </li>
      ))}
      {(change.labels?.length ?? 0) > 8 && <li>…</li>}
    </ol>
  );
}

/** Every proposed change, labeled. Unsupported ones show why and can't be accepted. */
export function ChangeList({ changes, onDecide, readOnly = false, busy = false }: Props) {
  return (
    <ul className="grid gap-3" aria-label="Proposed changes">
      {changes.map((change) => {
        const unsupported = change.status === "unsupported";
        const decision = change.decision ?? "pending";
        return (
          <li
            key={change.id}
            aria-label={change.title}
            className={cn(
              "grid gap-2 rounded-lg border p-3",
              unsupported && "border-destructive/40 bg-destructive/5",
              decision === "accepted" && "border-primary/50 bg-primary/5",
              decision === "rejected" && "opacity-60",
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={change.source === "ai" ? "secondary" : "outline"}>
                {change.source === "ai" ? "AI suggestion" : "Rule-based"}
              </Badge>
              {unsupported && <Badge variant="destructive">Unsupported</Badge>}
              <span className="text-sm font-medium">{change.title}</span>
            </div>
            <Detail change={change} />
            {change.reason && <p className="text-xs text-muted-foreground">Why: {change.reason}</p>}
            {unsupported && (
              <ul className="grid gap-1 text-xs text-destructive" aria-label="Problems">
                {(change.issues ?? []).map((issue, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden /> {issue}
                  </li>
                ))}
              </ul>
            )}
            {!readOnly && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={decision === "accepted" ? "default" : "outline"}
                  aria-pressed={decision === "accepted"}
                  disabled={unsupported || busy}
                  title={unsupported ? "Unsupported changes can't be accepted" : undefined}
                  onClick={() =>
                    onDecide(change.id, decision === "accepted" ? "pending" : "accepted")
                  }
                >
                  <Check /> Accept
                </Button>
                <Button
                  size="sm"
                  variant={decision === "rejected" ? "secondary" : "ghost"}
                  aria-pressed={decision === "rejected"}
                  disabled={busy}
                  onClick={() =>
                    onDecide(change.id, decision === "rejected" ? "pending" : "rejected")
                  }
                >
                  <X /> Reject
                </Button>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
