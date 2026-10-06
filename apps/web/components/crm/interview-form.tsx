"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { NewInterview } from "@/lib/api/crm";
import { INTERVIEW_KINDS } from "@/lib/crm";

type Props = { onSubmit: (body: NewInterview) => Promise<unknown>; error?: string | null };

export function InterviewForm({ onSubmit, error }: Props) {
  const [when, setWhen] = useState("");
  const [kind, setKind] = useState<NewInterview["kind"]>("phone_screen");
  const [location, setLocation] = useState("");
  const [checklist, setChecklist] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const date = new Date(when);
    if (!when || Number.isNaN(date.getTime())) {
      setProblem("Choose the interview date and time.");
      return;
    }
    setProblem(null);
    try {
      await onSubmit({
        // The browser's local time, sent with its timezone.
        scheduled_at: date.toISOString(),
        kind,
        ...(location.trim() ? { location: location.trim() } : {}),
        checklist: checklist
          .split("\n")
          .map((t) => t.trim())
          .filter(Boolean)
          .slice(0, 30)
          .map((text) => ({ text: text.slice(0, 200), done: false })),
      });
      setWhen("");
      setLocation("");
      setChecklist("");
    } catch {
      // Shown through `error`.
    }
  };

  return (
    <form onSubmit={submit} noValidate className="grid gap-3 rounded-lg border p-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="grid gap-1">
          <Label htmlFor="iv-when">Date and time</Label>
          <Input
            id="iv-when"
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="iv-kind">Type</Label>
          <select
            id="iv-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as NewInterview["kind"])}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            {INTERVIEW_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor="iv-where">Where (link or place)</Label>
          <Input id="iv-where" value={location} onChange={(e) => setLocation(e.target.value)} />
        </div>
      </div>
      <div className="grid gap-1">
        <Label htmlFor="iv-checklist">Preparation checklist (one item per line)</Label>
        <textarea
          id="iv-checklist"
          value={checklist}
          onChange={(e) => setChecklist(e.target.value)}
          className="min-h-16 rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs"
        />
      </div>
      {(problem ?? error) && (
        <p role="alert" className="text-sm text-destructive">
          {problem ?? error}
        </p>
      )}
      <div>
        <Button type="submit" size="sm">
          Add interview
        </Button>
      </div>
    </form>
  );
}
