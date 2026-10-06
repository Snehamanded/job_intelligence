"use client";

import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { WriteLetterButton } from "@/components/cover-letters/write-letter-button";
import { TrackControl } from "@/components/crm/track-control";
import { TailorButton } from "@/components/tailoring/tailor-button";
import { EligibilityList } from "@/components/jobs/eligibility-list";
import { MatchBadge } from "@/components/jobs/match-badge";
import { MatchBreakdown } from "@/components/jobs/match-breakdown";
import { PriorityControl } from "@/components/jobs/priority-control";
import { SkillsList } from "@/components/jobs/skills-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDeleteJob, useJob, useSetPriority } from "@/lib/api/jobs";
import {
  EMPLOYMENT_LABEL,
  SOURCE_LABEL,
  formatExperience,
  formatPosted,
  formatSalary,
  sourceLinkRel,
} from "@/lib/jobs-format";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const job = useJob(id);
  const remove = useDeleteJob();
  const setPriority = useSetPriority();

  if (job.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (job.error || !job.data) {
    return <p role="alert">{job.error?.message ?? "Job not found"}</p>;
  }
  const j = job.data;
  const facts: [string, string | null][] = [
    ["Location", (j.locations ?? []).join(" · ") || null],
    ["Salary", formatSalary(j) ?? "Not listed"],
    ["Salary as written", j.salary_text ?? null],
    ["Experience", formatExperience(j)],
    ["Type", EMPLOYMENT_LABEL[j.employment_type] ?? "Not stated"],
    ["Posted", formatPosted(j.posted_at)],
  ];

  return (
    <div className="grid max-w-3xl gap-6">
      <Link
        href="/jobs"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="size-4" /> All jobs
      </Link>
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{j.title}</h1>
          {j.is_mock && <Badge variant="warning">Mock data</Badge>}
        </div>
        <p className="text-muted-foreground">{j.company}</p>
        <p className="text-xs text-muted-foreground">
          Source: {SOURCE_LABEL[j.source] ?? j.source}
          {(j.also_seen_on ?? []).length > 0 &&
            ` · also on ${(j.also_seen_on ?? []).map((s) => SOURCE_LABEL[s.source] ?? s.source).join(", ")}`}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {j.url && (
          <Button asChild>
            <a href={j.url} target="_blank" rel={sourceLinkRel(j.source)}>
              View on {SOURCE_LABEL[j.source] ?? j.source} <ExternalLink />
            </a>
          </Button>
        )}
        <Button
          variant="outline"
          disabled={remove.isPending}
          onClick={() => remove.mutate(j.id, { onSuccess: () => router.replace("/jobs") })}
        >
          Remove from my list
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <TrackControl job={j} />
        <TailorButton jobId={j.id} />
        <WriteLetterButton jobId={j.id} />
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">Your priority</span>
        <PriorityControl
          value={j.priority}
          disabled={setPriority.isPending}
          onChange={(priority) => setPriority.mutate({ id: j.id, priority })}
        />
      </div>

      {j.match ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-3">
              Match
              <MatchBadge match={j.match} size="lg" />
              {j.match.high_priority && <Badge variant="success">High priority</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-6">
            <div className="grid gap-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {j.match.explanation_source === "ai" ? "AI-written summary" : "Summary"}
              </p>
              <p className="text-sm leading-relaxed">{j.match.explanation}</p>
            </div>
            <MatchBreakdown components={j.match.components} />
            <div className="grid gap-2">
              <h3 className="text-sm font-semibold">Skills in this posting</h3>
              <SkillsList skills={j.match.skills} />
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">Not scored yet.</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Fit with your preferences
            <Badge variant={j.eligibility.eligible ? "success" : "destructive"}>
              {j.eligibility.eligible ? "Eligible" : "Not eligible"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <EligibilityList checks={j.eligibility.checks} />
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {facts
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Plain text from the source; never rendered as HTML. */}
          <div className="text-sm leading-relaxed whitespace-pre-line">{j.description_text}</div>
        </CardContent>
      </Card>
    </div>
  );
}
