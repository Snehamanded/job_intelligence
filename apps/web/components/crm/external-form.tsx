"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Stage } from "@/lib/api/client";
import type { NewApplication } from "@/lib/api/crm";
import { STAGES } from "@/lib/crm";

type Props = { onSubmit: (body: NewApplication) => Promise<unknown>; error?: string | null };

export function ExternalApplicationForm({ onSubmit, error }: Props) {
  const [v, setV] = useState({
    title: "",
    company: "",
    location: "",
    url: "",
    stage: "applied" as Stage,
  });
  const [problem, setProblem] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!v.title.trim() || !v.company.trim()) return setProblem("Enter the job title and company.");
    if (v.url.trim() && !/^https?:\/\//.test(v.url.trim())) {
      return setProblem("The link must start with http:// or https://");
    }
    setProblem(null);
    try {
      await onSubmit({
        title: v.title.trim(),
        company: v.company.trim(),
        stage: v.stage,
        ...(v.location.trim() ? { location: v.location.trim() } : {}),
        ...(v.url.trim() ? { url: v.url.trim() } : {}),
      });
      setV({ title: "", company: "", location: "", url: "", stage: "applied" });
    } catch {
      // Shown through `error`.
    }
  };

  const field = (key: "title" | "company" | "location" | "url", label: string) => (
    <div className="grid gap-1">
      <Label htmlFor={`ext-${key}`}>{label}</Label>
      <Input
        id={`ext-${key}`}
        value={v[key]}
        onChange={(e) => setV({ ...v, [key]: e.target.value })}
      />
    </div>
  );

  return (
    <form onSubmit={submit} noValidate className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {field("title", "Job title")}
        {field("company", "Company")}
        {field("location", "Location (optional)")}
        {field("url", "Link (optional)")}
        <div className="grid gap-1">
          <Label htmlFor="ext-stage">Stage</Label>
          <select
            id="ext-stage"
            value={v.stage}
            onChange={(e) => setV({ ...v, stage: e.target.value as Stage })}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {(problem ?? error) && (
        <p role="alert" className="text-sm text-destructive">
          {problem ?? error}
        </p>
      )}
      <div>
        <Button type="submit">Add to board</Button>
      </div>
    </form>
  );
}
