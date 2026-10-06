import type { ApplicationDetail } from "@/lib/api/client";
import { STAGE_LABEL } from "@/lib/crm";

function describe(e: ApplicationDetail["events"][number]): string {
  switch (e.kind) {
    case "created":
      return `Added as ${e.to_stage ? STAGE_LABEL[e.to_stage] : "saved"}`;
    case "stage_changed":
      return `${e.from_stage ? STAGE_LABEL[e.from_stage] : "?"} → ${e.to_stage ? STAGE_LABEL[e.to_stage] : "?"}${
        e.detail ? ` (${e.detail})` : ""
      }`;
    case "interview_added":
      return `Interview added${e.detail ? `: ${e.detail}` : ""}`;
    case "interview_outcome":
      return `Interview ${e.detail ?? "updated"}`;
    default:
      return e.kind;
  }
}

export function Timeline({ events }: { events: ApplicationDetail["events"] }) {
  return (
    <ol className="grid gap-2 border-l pl-4 text-sm" aria-label="History">
      {[...events].reverse().map((e) => (
        <li key={e.id} className="relative">
          <span
            className="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-primary"
            aria-hidden
          />
          <p>{describe(e)}</p>
          <p className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString()}</p>
        </li>
      ))}
    </ol>
  );
}
