"use client";

import { Bookmark, Send } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { JobDetail } from "@/lib/api/client";
import { useCreateApplication } from "@/lib/api/crm";
import { STAGE_LABEL } from "@/lib/crm";

/** Save a job to the board, or record that you applied on the employer's site. */
export function TrackControl({ job }: { job: JobDetail }) {
  const create = useCreateApplication();
  if (job.application) {
    return (
      <Link
        href={`/applications/${job.application.id}`}
        className="inline-flex items-center gap-2 text-sm"
      >
        <Badge variant="secondary">{STAGE_LABEL[job.application.stage]}</Badge>
        <span className="text-primary underline-offset-4 hover:underline">View application</span>
      </Link>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        disabled={create.isPending}
        onClick={() => create.mutate({ job_id: job.id, stage: "saved" })}
      >
        <Bookmark /> Save
      </Button>
      <Button
        variant="outline"
        disabled={create.isPending}
        onClick={() => create.mutate({ job_id: job.id, stage: "applied" })}
      >
        <Send /> I applied
      </Button>
      {create.error && <span className="text-sm text-destructive">{create.error.message}</span>}
    </div>
  );
}
