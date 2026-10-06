"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState, type ChangeEvent, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { ImportBatch, ImportChannel } from "@/lib/api/client";
import { useImportBatch, useStartImport } from "@/lib/api/jobs";
import { cn } from "@/lib/utils";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

const CHANNELS: { value: ImportChannel; label: string; help: string }[] = [
  {
    value: "email",
    label: "Job alert emails",
    help: "Open a LinkedIn, Naukri or Indeed job alert email, select all, copy and paste it here. Several emails at once are fine.",
  },
  {
    value: "whatsapp",
    label: "WhatsApp",
    help: "Copy the job messages, or upload a chat export: in the chat, tap ⋮ (or the name) → More → Export chat → Without media, and choose the .txt file. For a channel, forward its posts to a chat (for example, one with yourself) and export that. Names and phone numbers are removed and the text is deleted after import.",
  },
  {
    value: "other",
    label: "Other",
    help: "Any text with several job posts, such as a newsletter or a forum thread.",
  },
];

const STATUS: Record<
  ImportBatch["results"][number]["status"],
  { label: string; variant: "success" | "secondary" | "outline" | "destructive" }
> = {
  new: { label: "Added", variant: "success" },
  imported: { label: "Added from link", variant: "success" },
  updated: { label: "Updated", variant: "secondary" },
  duplicate: { label: "Already added", variant: "outline" },
  failed: { label: "Failed", variant: "destructive" },
};

const textarea =
  "min-h-56 w-full rounded-md border border-input bg-transparent px-3 py-2 font-mono text-xs shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function BulkImportForm() {
  const [channel, setChannel] = useState<ImportChannel>("email");
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const start = useStartImport();
  const batch = useImportBatch(batchId);
  const running = batch.data?.status === "queued" || batch.data?.status === "running";

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setProblem("That file is too large. Export the chat without media.");
      return;
    }
    setText(await file.text());
    setChannel("whatsapp");
    setProblem(null);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (text.trim().length < 30) {
      setProblem("Paste the job posts first.");
      return;
    }
    setProblem(null);
    start.mutate(
      { channel, text },
      {
        onSuccess: (b) => {
          setBatchId(b.id);
          setText("");
        },
      },
    );
  };

  const help = CHANNELS.find((c) => c.value === channel)?.help;
  return (
    <div className="grid gap-4">
      <form onSubmit={submit} noValidate className="grid gap-4">
        <div
          role="radiogroup"
          aria-label="Where the posts are from"
          className="flex flex-wrap gap-1"
        >
          {CHANNELS.map((c) => (
            <button
              key={c.value}
              type="button"
              role="radio"
              aria-checked={channel === c.value}
              onClick={() => setChannel(c.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium",
                channel === c.value
                  ? "bg-accent text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{help}</p>
        <div className="grid gap-2">
          <Label htmlFor="bulk-text">Pasted posts</Label>
          <textarea
            id="bulk-text"
            className={textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste here…"
          />
        </div>
        {(problem ?? start.error?.message) && (
          <p role="alert" className="text-sm text-destructive">
            {problem ?? start.error?.message}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={start.isPending || running}>
            {start.isPending || running ? "Importing…" : "Find and import jobs"}
          </Button>
          <Label className="cursor-pointer text-sm font-normal text-primary underline-offset-4 hover:underline">
            <input type="file" accept=".txt,text/plain" className="sr-only" onChange={onFile} />
            Upload a WhatsApp export (.txt)
          </Label>
        </div>
      </form>

      {batch.data && <ImportResults batch={batch.data} />}
    </div>
  );
}

function ImportResults({ batch }: { batch: ImportBatch }) {
  if (batch.status === "queued" || batch.status === "running") {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin" /> Finding job posts…
      </p>
    );
  }
  const added = batch.results.filter((r) => r.job_id != null && r.status !== "failed").length;
  return (
    <section aria-label="Import results" className="grid gap-3 border-t pt-4">
      <p className="text-sm font-medium" role="status">
        {batch.error_message ??
          `Found ${batch.results.length} job post${batch.results.length === 1 ? "" : "s"}; ${added} in your jobs.`}
      </p>
      {batch.notice && <p className="text-xs text-muted-foreground">{batch.notice}</p>}
      <ul className="divide-y">
        {batch.results.map((r, i) => (
          <li key={`${r.job_id ?? "x"}-${i}`} className="grid gap-1 py-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={STATUS[r.status].variant}>{STATUS[r.status].label}</Badge>
              {r.job_id ? (
                <Link href={`/jobs/${r.job_id}`} className="font-medium hover:underline">
                  {r.title}
                </Link>
              ) : (
                <span className="font-medium">{r.title}</span>
              )}
              {r.company && <span className="text-muted-foreground">· {r.company}</span>}
            </div>
            {r.note && <p className="text-xs text-muted-foreground">{r.note}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
