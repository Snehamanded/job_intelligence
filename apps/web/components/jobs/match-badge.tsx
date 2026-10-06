import type { MatchSummary } from "@/lib/api/client";
import { cn } from "@/lib/utils";

// One hue, stepped by band: ordinal magnitude, not status.
const BAND_STYLE: Record<MatchSummary["label"], string> = {
  Excellent: "bg-primary text-primary-foreground",
  Strong: "bg-primary/80 text-primary-foreground",
  Good: "bg-primary/20 text-foreground",
  Moderate: "bg-primary/10 text-foreground",
  Weak: "bg-muted text-muted-foreground",
};

export function MatchBadge({ match, size = "sm" }: { match: MatchSummary; size?: "sm" | "lg" }) {
  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1.5 rounded-md font-medium",
        size === "lg" ? "px-3 py-1.5 text-base" : "px-2 py-0.5 text-xs",
        BAND_STYLE[match.label],
      )}
      aria-label={`Match ${match.match_score} out of 100, ${match.label}`}
    >
      <span className={size === "lg" ? "text-2xl font-semibold" : "font-semibold"}>
        {match.match_score}
      </span>
      {match.label}
    </span>
  );
}
