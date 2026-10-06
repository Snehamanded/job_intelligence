import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";

import type { EligibilityCheck } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const ICON = { pass: CheckCircle2, fail: XCircle, unknown: CircleHelp };
const COLOR = {
  pass: "text-emerald-600",
  fail: "text-destructive",
  unknown: "text-muted-foreground",
};

export function EligibilityList({
  checks,
  compact = false,
}: {
  checks: EligibilityCheck[];
  compact?: boolean;
}) {
  const shown = compact ? checks.filter((c) => c.status !== "pass") : checks;
  if (shown.length === 0) return null;
  return (
    <ul className="grid gap-1" aria-label="Eligibility">
      {shown.map((check) => {
        const Icon = ICON[check.status];
        return (
          <li key={check.name} className="flex items-start gap-1.5 text-xs">
            <Icon className={cn("mt-px size-3.5 shrink-0", COLOR[check.status])} aria-hidden />
            <span
              className={check.status === "fail" ? "text-destructive" : "text-muted-foreground"}
            >
              {check.reason}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
