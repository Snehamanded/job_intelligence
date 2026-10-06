"use client";

import { ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { WriteLetterButton } from "@/components/cover-letters/write-letter-button";
import { InterviewsPanel } from "@/components/crm/interviews-panel";
import { NotesPanel } from "@/components/crm/notes-panel";
import { Timeline } from "@/components/crm/timeline";
import { TailorButton } from "@/components/tailoring/tailor-button";
import { MatchBadge } from "@/components/jobs/match-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { MatchSummary, Stage } from "@/lib/api/client";
import { useApplication, useDeleteApplication, useUpdateApplication } from "@/lib/api/crm";
import { STAGES } from "@/lib/crm";

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const application = useApplication(id);
  const update = useUpdateApplication();
  const remove = useDeleteApplication();
  const [nextAction, setNextAction] = useState<string | null>(null);
  const [nextDate, setNextDate] = useState<string | null>(null);

  if (application.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!application.data) return <p role="alert">{application.error?.message ?? "Not found"}</p>;
  const a = application.data;
  const match =
    a.match_score != null && a.match_label
      ? ({ match_score: a.match_score, label: a.match_label } as MatchSummary)
      : null;

  return (
    <div className="grid max-w-4xl gap-6">
      <Link
        href="/applications"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="size-4" /> Board
      </Link>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">{a.title}</h1>
          <p className="text-muted-foreground">
            {a.company}
            {a.location ? ` · ${a.location}` : ""}
          </p>
        </div>
        {match && <MatchBadge match={match} size="lg" />}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <Label htmlFor="stage">Stage</Label>
          <select
            id="stage"
            value={a.stage}
            onChange={(e) => update.mutate({ id: a.id, stage: e.target.value as Stage })}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor="applied-at">Applied on</Label>
          <Input
            id="applied-at"
            type="date"
            value={a.applied_at ?? ""}
            onChange={(e) => update.mutate({ id: a.id, applied_at: e.target.value || null })}
            className="w-40"
          />
        </div>
        {a.job_id && (
          <Button variant="outline" asChild>
            <Link href={`/jobs/${a.job_id}`}>Job details</Link>
          </Button>
        )}
        {a.job_id && <TailorButton jobId={a.job_id} />}
        {a.job_id && <WriteLetterButton jobId={a.job_id} />}
        {a.url && (
          <Button variant="outline" asChild>
            <a href={a.url} target="_blank" rel="noopener noreferrer nofollow">
              Posting <ExternalLink />
            </a>
          </Button>
        )}
        <Button
          variant="ghost"
          className="ml-auto text-destructive"
          onClick={() => {
            if (window.confirm("Remove this application and its notes and interviews?")) {
              remove.mutate(a.id, { onSuccess: () => router.replace("/applications") });
            }
          }}
        >
          Remove
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Next step</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              update.mutate({
                id: a.id,
                next_action: (nextAction ?? a.next_action ?? "").trim() || null,
                next_action_date: (nextDate ?? a.next_action_date) || null,
              });
            }}
          >
            <div className="grid min-w-64 flex-1 gap-1">
              <Label htmlFor="next-action">What&apos;s next</Label>
              <Input
                id="next-action"
                maxLength={300}
                value={nextAction ?? a.next_action ?? ""}
                onChange={(e) => setNextAction(e.target.value)}
                placeholder="Follow up with the recruiter"
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="next-date">By</Label>
              <Input
                id="next-date"
                type="date"
                value={nextDate ?? a.next_action_date ?? ""}
                onChange={(e) => setNextDate(e.target.value)}
                className="w-40"
              />
            </div>
            <Button type="submit" variant="outline">
              Save
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Interviews</CardTitle>
          </CardHeader>
          <CardContent>
            <InterviewsPanel application={a} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <NotesPanel application={a} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          <Timeline events={a.events} />
        </CardContent>
      </Card>
    </div>
  );
}
