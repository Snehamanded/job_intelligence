"use client";

import { Download, Loader2, RefreshCw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_URL, type Resume } from "@/lib/api/client";

const STATUS: Record<
  Resume["status"],
  { label: string; variant: "secondary" | "success" | "destructive" }
> = {
  queued: { label: "Queued", variant: "secondary" },
  parsing: { label: "Parsing", variant: "secondary" },
  parsed: { label: "Parsed", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

type Props = {
  resumes: Resume[];
  currentResumeId: string | null | undefined;
  onReparse: (id: string) => void;
  onDelete: (id: string) => void;
  busyId?: string | null;
};

export function ResumeList({ resumes, currentResumeId, onReparse, onDelete, busyId }: Props) {
  if (resumes.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your resumes</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {resumes.map((resume) => {
            const status = STATUS[resume.status];
            const working = resume.status === "queued" || resume.status === "parsing";
            return (
              <li
                key={resume.id}
                className="flex flex-wrap items-start gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium">{resume.original_filename}</span>
                    <Badge variant={status.variant}>
                      {working && <Loader2 className="animate-spin" />}
                      {status.label}
                    </Badge>
                    {resume.id === currentResumeId && <Badge variant="outline">In use</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {resume.file_type.toUpperCase()} · {(resume.size_bytes / 1024).toFixed(0)} KB ·
                    uploaded {new Date(resume.created_at).toLocaleString()}
                  </p>
                  {resume.error_message && (
                    <p className="mt-1 text-sm text-destructive">{resume.error_message}</p>
                  )}
                  {resume.parse_notice && (
                    <p className="mt-1 text-sm text-amber-700">{resume.parse_notice}</p>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" asChild aria-label="Download">
                    <a href={`${API_URL}/api/resumes/${resume.id}/file`}>
                      <Download />
                    </a>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Parse again"
                    disabled={working || busyId === resume.id}
                    onClick={() => onReparse(resume.id)}
                  >
                    <RefreshCw />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete resume"
                    disabled={busyId === resume.id}
                    onClick={() => {
                      if (window.confirm(`Delete ${resume.original_filename}?`))
                        onDelete(resume.id);
                    }}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
