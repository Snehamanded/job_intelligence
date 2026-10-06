"use client";

import { ArrowLeft, Download, Loader2, Printer } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { LetterPreview } from "@/components/cover-letters/letter-preview";
import { SentenceEditor } from "@/components/cover-letters/sentence-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  coverLetterDocxUrl,
  useCoverLetter,
  useDeleteCoverLetter,
  useEditSentences,
  useSaveCoverLetter,
} from "@/lib/api/cover-letters";

export default function CoverLetterPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const letter = useCoverLetter(id);
  const edit = useEditSentences(id);
  const save = useSaveCoverLetter(id);
  const remove = useDeleteCoverLetter();
  const [name, setName] = useState<string | null>(null);

  if (letter.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!letter.data) return <p role="alert">{letter.error?.message ?? "Not found"}</p>;
  const l = letter.data;
  const saved = l.status === "saved";
  const sentences = l.paragraphs.flatMap((p) => p.sentences ?? []);
  const unsupported = sentences.filter((s) => s.status === "unsupported").length;

  return (
    <div className="grid gap-6">
      <Link
        href="/cover-letters"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="size-4" /> Cover letters
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          v{l.version} · {l.name}
        </h1>
        <Badge variant={saved ? "success" : "secondary"}>{saved ? "Saved" : l.status}</Badge>
        <Badge variant="outline">
          {l.tone} · {l.length}
        </Badge>
      </div>
      {l.status === "generating" && (
        <p className="flex items-center gap-2 text-sm" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Writing and fact-checking every sentence…
        </p>
      )}
      {l.status === "failed" && (
        <p role="alert" className="text-sm text-destructive">
          {l.notice}
        </p>
      )}
      {l.notice && l.status !== "failed" && <p className="text-sm text-amber-700">{l.notice}</p>}

      {(l.status === "ready" || saved) && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>{saved ? "Sentences" : "Review sentences"}</CardTitle>
              <CardDescription>
                Statements about you must cite your resume; statements about the company must quote
                the posting.
                {unsupported > 0 &&
                  ` ${unsupported} unsupported sentence${unsupported === 1 ? " was" : "s were"} left out.`}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <SentenceEditor
                paragraphs={l.paragraphs}
                readOnly={saved}
                busy={edit.isPending}
                onEdit={(edits) => edit.mutate(edits)}
              />
              {edit.error && (
                <p role="alert" className="text-sm text-destructive">
                  {edit.error.message}
                </p>
              )}
            </CardContent>
          </Card>
          <div className="grid content-start gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{saved ? "Saved letter" : "Preview"}</CardTitle>
              </CardHeader>
              <CardContent>
                <LetterPreview company={l.company} paragraphs={l.preview} signature={l.signature} />
              </CardContent>
            </Card>
            {saved ? (
              <div className="flex flex-wrap gap-2">
                <Button asChild>
                  <a href={coverLetterDocxUrl(l.id)}>
                    <Download /> Download DOCX
                  </a>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/print/cover-letters/${l.id}`} target="_blank">
                    <Printer /> Print or save as PDF
                  </Link>
                </Button>
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
                  <label htmlFor="letter-name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input
                    id="letter-name"
                    value={name ?? l.name}
                    maxLength={200}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <Button type="submit" disabled={save.isPending || l.preview.length === 0}>
                  Save letter
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
                  if (window.confirm("Delete this cover letter?")) {
                    remove.mutate(l.id, { onSuccess: () => router.replace("/cover-letters") });
                  }
                }}
              >
                Delete letter
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
