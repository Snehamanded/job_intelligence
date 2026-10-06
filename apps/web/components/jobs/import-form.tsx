"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ImportBody } from "@/lib/api/jobs";
import { cn } from "@/lib/utils";

type Props = {
  onImport: (body: ImportBody) => Promise<unknown>;
  pending?: boolean;
  error?: string | null;
};

const textarea =
  "min-h-48 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function ImportForm({ onImport, pending = false, error }: Props) {
  const [mode, setMode] = useState<"url" | "text">("url");
  const [values, setValues] = useState({
    url: "",
    title: "",
    company: "",
    location: "",
    description: "",
  });
  const [problem, setProblem] = useState<string | null>(null);
  const set = (key: keyof typeof values) => (v: string) => setValues((s) => ({ ...s, [key]: v }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    let body: ImportBody;
    if (mode === "url") {
      if (
        !/^https:\/\/(job-boards|boards)(\.eu)?\.greenhouse\.io\/[^/]+\/jobs\/\d+/.test(
          values.url.trim(),
        )
      ) {
        setProblem(
          "Paste a Greenhouse job link, e.g. https://job-boards.greenhouse.io/company/jobs/123.",
        );
        return;
      }
      body = { url: values.url.trim() };
    } else {
      if (!values.title.trim() || !values.company.trim()) {
        setProblem("Title and company are required.");
        return;
      }
      if (values.description.trim().length < 50) {
        setProblem("Paste the full job description (at least 50 characters).");
        return;
      }
      body = {
        title: values.title.trim(),
        company: values.company.trim(),
        location: values.location.trim(),
        description: values.description,
        ...(values.url.trim() ? { url: values.url.trim() } : {}),
      };
    }
    setProblem(null);
    try {
      await onImport(body);
    } catch {
      // Shown through `error`.
    }
  };

  const tab = (value: "url" | "text", label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === value}
      onClick={() => {
        setMode(value);
        setProblem(null);
      }}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium",
        mode === value ? "bg-accent text-primary" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );

  return (
    <form onSubmit={submit} noValidate className="grid gap-4">
      <div role="tablist" className="flex gap-1">
        {tab("url", "Greenhouse link")}
        {tab("text", "Paste description")}
      </div>
      {mode === "url" ? (
        <div className="grid gap-2">
          <Label htmlFor="import-url">Job link</Label>
          <Input
            id="import-url"
            value={values.url}
            onChange={(e) => set("url")(e.target.value)}
            placeholder="https://job-boards.greenhouse.io/company/jobs/123456"
          />
          <p className="text-xs text-muted-foreground">
            For LinkedIn, Naukri and other sites, copy the description into the other tab.
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="import-title">Job title</Label>
              <Input
                id="import-title"
                value={values.title}
                onChange={(e) => set("title")(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="import-company">Company</Label>
              <Input
                id="import-company"
                value={values.company}
                onChange={(e) => set("company")(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="import-location">Location</Label>
              <Input
                id="import-location"
                value={values.location}
                onChange={(e) => set("location")(e.target.value)}
                placeholder="Bengaluru, India or Remote, India"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="import-link">Link (optional)</Label>
              <Input
                id="import-link"
                value={values.url}
                onChange={(e) => set("url")(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="import-description">Job description</Label>
            <textarea
              id="import-description"
              className={textarea}
              value={values.description}
              onChange={(e) => set("description")(e.target.value)}
            />
          </div>
        </>
      )}
      {(problem ?? error) && (
        <p role="alert" className="text-sm text-destructive">
          {problem ?? error}
        </p>
      )}
      <div>
        <Button type="submit" disabled={pending}>
          {pending ? "Importing…" : "Import job"}
        </Button>
      </div>
    </form>
  );
}
