import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import type { MatchDetail } from "@/lib/api/client";

const GROUPS = [
  { status: "demonstrated", title: "On your resume", icon: CheckCircle2, tone: "text-emerald-600" },
  { status: "related", title: "Related experience", icon: CircleDashed, tone: "text-amber-600" },
  {
    status: "not_demonstrated",
    title: "Not on your resume",
    icon: XCircle,
    tone: "text-muted-foreground",
  },
] as const;

export function SkillsList({ skills }: { skills: MatchDetail["skills"] }) {
  if (skills.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No specific skills found in this posting.</p>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {GROUPS.map(({ status, title, icon: Icon, tone }) => {
        const items = skills.filter((s) => s.status === status);
        return (
          <section key={status} aria-label={title} className="grid content-start gap-2">
            <h4 className="flex items-center gap-1.5 text-sm font-medium">
              <Icon className={`size-4 ${tone}`} aria-hidden /> {title} ({items.length})
            </h4>
            <ul className="grid gap-1 text-sm">
              {items.map((s) => (
                <li key={s.name}>
                  {s.name}
                  {status === "related" && s.profile_skills.length > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      · via {s.profile_skills.join(", ")}
                    </span>
                  )}
                </li>
              ))}
              {items.length === 0 && <li className="text-muted-foreground">None</li>}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
