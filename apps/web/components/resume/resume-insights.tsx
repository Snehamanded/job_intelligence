"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { useProfile } from "@/lib/api/profile";
import { formatMonths } from "@/lib/resume-file";

export function ResumeInsights() {
  const { data: profile, isPending } = useProfile();
  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const data = profile?.data;
  if (
    !profile ||
    !data ||
    ((data.skills ?? []).length === 0 && (data.experience ?? []).length === 0)
  ) {
    return (
      <EmptyState icon={FileText} title="No resume uploaded">
        <Link href="/resume" className="text-primary underline-offset-4 hover:underline">
          Upload your resume
        </Link>{" "}
        to see a summary of your profile here.
      </EmptyState>
    );
  }

  const latest = (data.experience ?? [])[0];
  const excluded = (data.unsupported ?? []).length;
  return (
    <div className="grid gap-4 text-sm">
      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border bg-muted/40 p-3">
          <dt className="text-xs text-muted-foreground">Experience</dt>
          <dd className="mt-1 text-lg font-semibold">{formatMonths(profile.experience_months)}</dd>
        </div>
        <div className="rounded-lg border bg-muted/40 p-3">
          <dt className="text-xs text-muted-foreground">Skills</dt>
          <dd className="mt-1 text-lg font-semibold">{(data.skills ?? []).length}</dd>
        </div>
      </dl>
      {latest && (
        <p>
          Latest role: <strong>{latest.title}</strong> at {latest.company}
        </p>
      )}
      <ul className="flex flex-wrap gap-1.5">
        {(data.skills ?? []).slice(0, 12).map((skill) => (
          <li key={skill.name}>
            <Badge variant="secondary">{skill.name}</Badge>
          </li>
        ))}
      </ul>
      {excluded > 0 && (
        <p className="text-amber-700">
          {excluded} suggested item{excluded === 1 ? " was" : "s were"} excluded because the resume
          does not support {excluded === 1 ? "it" : "them"}.{" "}
          <Link href="/resume" className="underline underline-offset-4">
            Review
          </Link>
        </p>
      )}
    </div>
  );
}
