import { Badge } from "@/components/ui/badge";
import type { MatchDetail } from "@/lib/api/client";

const ORDER = ["skills", "experience", "role", "location", "projects", "industry", "preferences"];
const LABEL: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  role: "Role",
  location: "Location",
  projects: "Projects",
  industry: "Industry",
  preferences: "Preferences",
};
const METHOD: Record<string, string> = {
  ai: "AI",
  embedding: "similarity",
  code: "rule",
  unknown: "unknown",
};

/** One meter per component. Values and details are text, so this doubles as the table view. */
export function MatchBreakdown({ components }: { components: MatchDetail["components"] }) {
  const rows = ORDER.filter((k) => components[k]).map((k) => [k, components[k]] as const);
  return (
    <ul className="grid gap-3" aria-label="Score breakdown">
      {rows.map(([key, c]) => (
        <li key={key} className="grid gap-1" title={c.detail}>
          <div className="flex items-baseline gap-2 text-sm">
            <span className="font-medium">{LABEL[key]}</span>
            <span className="text-xs text-muted-foreground">weight {c.weight}</span>
            <Badge variant="outline" className="text-[10px]">
              {METHOD[c.method]}
            </Badge>
            <span className="ml-auto font-medium tabular-nums">{c.score}</span>
          </div>
          <div
            role="meter"
            aria-label={`${LABEL[key]} score`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={c.score}
            className="h-2 overflow-hidden rounded-full bg-primary/15"
          >
            <div className="h-full rounded-full bg-primary" style={{ width: `${c.score}%` }} />
          </div>
          <p className="text-xs text-muted-foreground">{c.detail}</p>
        </li>
      ))}
    </ul>
  );
}
