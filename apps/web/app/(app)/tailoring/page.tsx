"use client";

import { PenLine } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { useTailoringList } from "@/lib/api/tailoring";

const STATUS = {
  generating: "Generating",
  ready: "Ready to review",
  failed: "Failed",
  saved: "Saved",
} as const;

export default function TailoringPage() {
  const versions = useTailoringList();
  return (
    <>
      <PageHeader
        title="Tailored resumes"
        description="Start from a job: open it and choose “Tailor resume”. Every change needs your approval and must be backed by your resume."
      />
      {versions.data && versions.data.length === 0 ? (
        <EmptyState icon={PenLine} title="No tailored resumes yet">
          Open a job from{" "}
          <Link href="/jobs" className="text-primary underline">
            Jobs
          </Link>{" "}
          and choose Tailor resume.
        </EmptyState>
      ) : (
        <ul className="grid max-w-3xl gap-2">
          {(versions.data ?? []).map((v) => (
            <li key={v.id}>
              <Link
                href={`/tailoring/${v.id}`}
                className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-3 hover:bg-accent"
              >
                <span className="text-sm font-medium">
                  v{v.version} · {v.name}
                </span>
                <Badge
                  variant={
                    v.status === "saved"
                      ? "success"
                      : v.status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {STATUS[v.status]}
                </Badge>
                <Badge variant="outline">{v.method === "ai" ? "AI + rules" : "Rules only"}</Badge>
                <span className="ml-auto text-xs text-muted-foreground">
                  {new Date(v.created_at).toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
