"use client";

import { Mail } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { useCoverLetters } from "@/lib/api/cover-letters";

export default function CoverLettersPage() {
  const letters = useCoverLetters();
  return (
    <>
      <PageHeader
        title="Cover letters"
        description="Start from a job: open it and choose “Write cover letter”. Every sentence is checked against your resume or the job posting."
      />
      {letters.data && letters.data.length === 0 ? (
        <EmptyState icon={Mail} title="No cover letters yet">
          Open a job from{" "}
          <Link href="/jobs" className="text-primary underline">
            Jobs
          </Link>{" "}
          and choose Write cover letter.
        </EmptyState>
      ) : (
        <ul className="grid max-w-3xl gap-2">
          {(letters.data ?? []).map((l) => (
            <li key={l.id}>
              <Link
                href={`/cover-letters/${l.id}`}
                className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-3 hover:bg-accent"
              >
                <span className="text-sm font-medium">
                  v{l.version} · {l.name}
                </span>
                <Badge
                  variant={
                    l.status === "saved"
                      ? "success"
                      : l.status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {l.status === "ready" ? "Ready to review" : l.status}
                </Badge>
                <Badge variant="outline">{l.method === "ai" ? "AI draft" : "Template"}</Badge>
                <span className="ml-auto text-xs text-muted-foreground">
                  {new Date(l.created_at).toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
