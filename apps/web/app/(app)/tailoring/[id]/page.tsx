"use client";

import { ArrowLeft, Download, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ChangeList } from "@/components/tailoring/change-list";
import { ResumePreview } from "@/components/tailoring/resume-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  docxUrl,
  pdfUrl,
  useDecide,
  useDeleteVersion,
  useSaveVersion,
  useTailoring,
} from "@/lib/api/tailoring";

export default function TailoringVersionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const version = useTailoring(id);
  const decide = useDecide(id);
  const save = useSaveVersion(id);
  const remove = useDeleteVersion();
  const [name, setName] = useState<string | null>(null);

  if (version.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!version.data) return <p role="alert">{version.error?.message ?? "Not found"}</p>;
  const v = version.data;
  const saved = v.status === "saved";
  const accepted = v.changes.filter((c) => c.decision === "accepted").length;
  const unsupported = v.changes.filter((c) => c.status === "unsupported").length;

  return (
    <div className="grid gap-6">
      <Link
        href="/tailoring"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="size-4" /> Tailored resumes
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          v{v.version} · {v.name}
        </h1>
        <Badge variant={saved ? "success" : "secondary"}>{saved ? "Saved" : v.status}</Badge>
        {v.job_id && (
          <Link
            href={`/jobs/${v.job_id}`}
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            View job
          </Link>
        )}
      </div>

      {v.status === "generating" && (
        <p className="flex items-center gap-2 text-sm" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Preparing suggestions and checking them
          against your resume…
        </p>
      )}
      {v.status === "failed" && (
        <p role="alert" className="text-sm text-destructive">
          {v.notice}
        </p>
      )}
      {v.notice && v.status !== "failed" && <p className="text-sm text-amber-700">{v.notice}</p>}

      {(v.status === "ready" || saved) && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="grid content-start gap-6">
            <Card>
              <CardHeader>
                <CardTitle>{saved ? "Changes" : "Review changes"}</CardTitle>
                <CardDescription>
                  {saved
                    ? `${accepted} change${accepted === 1 ? "" : "s"} applied.`
                    : "Nothing changes until you accept it. Unsupported suggestions claim something your resume doesn't say, so they can't be used."}
                  {unsupported > 0 && !saved && ` ${unsupported} unsupported.`}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {v.changes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No changes to suggest for this job.
                  </p>
                ) : (
                  <ChangeList
                    changes={v.changes}
                    readOnly={saved}
                    busy={decide.isPending}
                    onDecide={(changeId, decision) => decide.mutate({ [changeId]: decision })}
                  />
                )}
                {decide.error && (
                  <p role="alert" className="text-sm text-destructive">
                    {decide.error.message}
                  </p>
                )}
              </CardContent>
            </Card>
            {v.skill_gaps.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Skills this job mentions that your resume doesn&apos;t show</CardTitle>
                  <CardDescription>
                    Not added to your resume. If you genuinely have one, add it to your profile
                    first.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-wrap gap-2 text-sm">
                    {v.skill_gaps.map((g) => (
                      <li key={g.name}>
                        <Badge variant="outline">
                          {g.name}
                          {g.status === "related" && (g.profile_skills ?? []).length > 0
                            ? ` · related: ${g.profile_skills!.join(", ")}`
                            : ""}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="grid content-start gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{saved ? "Saved resume" : "Preview"}</CardTitle>
                {!saved && (
                  <CardDescription>
                    Highlighted bullets were reworded by AI (hover to see the original).
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>{v.preview && <ResumePreview doc={v.preview} highlight />}</CardContent>
            </Card>
            {saved ? (
              <div className="flex flex-wrap gap-2">
                <Button asChild>
                  <a href={pdfUrl(v.id)}>
                    <Download /> Download PDF
                  </a>
                </Button>
                <Button variant="outline" asChild>
                  <a href={docxUrl(v.id)}>
                    <Download /> Download DOCX
                  </a>
                </Button>
                <p className="basis-full text-xs text-muted-foreground">
                  Downloads keep the layout of the resume you uploaded (PDF or Word). A resume
                  uploaded as plain text gets a classic one-column layout.
                </p>
              </div>
            ) : (
              <form
                className="flex flex-wrap items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  save.mutate(name);
                }}
              >
                <div className="grid flex-1 gap-1">
                  <label htmlFor="version-name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input
                    id="version-name"
                    value={name ?? v.name}
                    onChange={(e) => setName(e.target.value)}
                    maxLength={200}
                  />
                </div>
                <Button type="submit" disabled={save.isPending}>
                  Save version ({accepted} change{accepted === 1 ? "" : "s"})
                </Button>
              </form>
            )}
            {save.error && (
              <p role="alert" className="text-sm text-destructive">
                {save.error.message}
              </p>
            )}
            <div>
              <Button
                variant="ghost"
                className="text-destructive"
                onClick={() => {
                  if (window.confirm("Delete this version?")) {
                    remove.mutate(v.id, { onSuccess: () => router.replace("/tailoring") });
                  }
                }}
              >
                Delete version
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
