"use client";

import { Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  useAddJobSource,
  useConnectors,
  useDeleteJobSource,
  useJobSources,
  type NewJobSource,
} from "@/lib/api/jobs";
import { SOURCE_LABEL } from "@/lib/jobs-format";

const BOARD_HELP: Record<string, string> = {
  greenhouse: "the part after greenhouse.io/ in the careers link, e.g. gitlab",
  lever: "the part after jobs.lever.co/, e.g. palantir",
  ashby: "the part after jobs.ashbyhq.com/, e.g. ramp",
};

export default function SourcesPage() {
  const sources = useJobSources();
  const connectors = useConnectors();
  const add = useAddJobSource();
  const remove = useDeleteJobSource();
  const [board, setBoard] = useState<{
    source: "greenhouse" | "lever" | "ashby";
    identifier: string;
    name: string;
  }>({
    source: "greenhouse",
    identifier: "",
    name: "",
  });
  const [country, setCountry] = useState("in");

  const configs = sources.data ?? [];
  const boards = configs.filter((c) => ["greenhouse", "lever", "ashby"].includes(c.source));
  const byName = Object.fromEntries((connectors.data ?? []).map((c) => [c.name, c]));
  const toggles = (connectors.data ?? []).filter((c) => c.config === "toggle");
  const adzuna = byName["adzuna"];

  const addBoard = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(
      {
        source: board.source,
        identifier: board.identifier.trim(),
        display_name: board.name.trim() || null,
      },
      { onSuccess: () => setBoard({ ...board, identifier: "", name: "" }) },
    );
  };

  const toggle = (source: NewJobSource["source"], on: boolean) => {
    const existing = configs.find((c) => c.source === source);
    if (on && !existing) add.mutate({ source });
    if (!on && existing) remove.mutate(existing.id);
  };

  return (
    <>
      <PageHeader title="Job sources" description="Where searches look for jobs." />
      <div className="grid max-w-3xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Company job boards</CardTitle>
            <CardDescription>
              Many companies list jobs on Greenhouse, Lever or Ashby. Add a company by the name in
              its careers link.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <form
              onSubmit={addBoard}
              className="grid gap-3 sm:grid-cols-[8rem_1fr_1fr_auto] sm:items-end"
            >
              <div className="grid gap-1">
                <Label htmlFor="board-source">Platform</Label>
                <select
                  id="board-source"
                  value={board.source}
                  onChange={(e) =>
                    setBoard({ ...board, source: e.target.value as typeof board.source })
                  }
                  className="h-9 rounded-md border bg-background px-2 text-sm"
                >
                  <option value="greenhouse">Greenhouse</option>
                  <option value="lever">Lever</option>
                  <option value="ashby">Ashby</option>
                </select>
              </div>
              <div className="grid gap-1">
                <Label htmlFor="board">Board name</Label>
                <Input
                  id="board"
                  value={board.identifier}
                  onChange={(e) => setBoard({ ...board, identifier: e.target.value })}
                  placeholder={BOARD_HELP[board.source].split("e.g. ")[1]}
                />
              </div>
              <div className="grid gap-1">
                <Label htmlFor="board-name">Company name (optional)</Label>
                <Input
                  id="board-name"
                  value={board.name}
                  onChange={(e) => setBoard({ ...board, name: e.target.value })}
                />
              </div>
              <Button type="submit" disabled={!board.identifier.trim() || add.isPending}>
                {add.isPending ? "Checking…" : "Add"}
              </Button>
            </form>
            <p className="text-xs text-muted-foreground">Board name: {BOARD_HELP[board.source]}.</p>
            {add.error && (
              <p role="alert" className="text-sm text-destructive">
                {add.error.message}
              </p>
            )}
            <ul className="divide-y" aria-label="Boards">
              {boards.map((s) => (
                <li key={s.id} className="flex items-center gap-3 py-2 text-sm">
                  <Badge variant="outline">{SOURCE_LABEL[s.source] ?? s.source}</Badge>
                  <span className="font-medium">{s.display_name}</span>
                  <code className="text-muted-foreground">{s.identifier}</code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ml-auto"
                    aria-label={`Remove ${s.display_name}`}
                    onClick={() => remove.mutate(s.id)}
                  >
                    <Trash2 />
                  </Button>
                </li>
              ))}
              {boards.length === 0 && (
                <li className="py-2 text-sm text-muted-foreground">No boards added yet.</li>
              )}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Remote job feeds</CardTitle>
            <CardDescription>
              Global remote jobs. Each links back to its original listing.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {toggles.map((c) => {
              const config = configs.find((s) => s.source === c.name);
              return (
                <div key={c.name} className="flex items-start gap-3">
                  <Switch
                    id={`feed-${c.name}`}
                    checked={Boolean(config)}
                    disabled={add.isPending || remove.isPending}
                    onCheckedChange={(on) => toggle(c.name as NewJobSource["source"], on)}
                  />
                  <div className="grid gap-0.5 text-sm">
                    <Label htmlFor={`feed-${c.name}`}>{c.label}</Label>
                    <p className="text-muted-foreground">{c.note}</p>
                    {config?.last_fetched_at && (
                      <p className="text-xs text-muted-foreground">
                        Last checked {new Date(config.last_fetched_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {adzuna && (
          <Card>
            <CardHeader>
              <CardTitle>Adzuna</CardTitle>
              <CardDescription>{adzuna.note}</CardDescription>
            </CardHeader>
            {adzuna.enabled && (
              <CardContent className="flex items-end gap-2">
                <div className="grid gap-1">
                  <Label htmlFor="adzuna-country">Country</Label>
                  <select
                    id="adzuna-country"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="h-9 rounded-md border bg-background px-2 text-sm"
                  >
                    <option value="in">India</option>
                    <option value="gb">United Kingdom</option>
                    <option value="us">United States</option>
                    <option value="sg">Singapore</option>
                  </select>
                </div>
                <Button
                  variant="outline"
                  onClick={() => add.mutate({ source: "adzuna", identifier: country })}
                >
                  Add
                </Button>
              </CardContent>
            )}
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>All sources</CardTitle>
            <CardDescription>
              Only sources with an official API or public feed are fetched automatically. Others can
              be added by importing individual jobs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-3">
              {(connectors.data ?? []).map((c) => (
                <li key={c.name} className="grid gap-1 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.label}</span>
                    <Badge variant={c.kind === "real" ? "success" : "secondary"}>
                      {c.kind === "real"
                        ? "Live"
                        : c.kind === "mock"
                          ? "Mock only"
                          : "Manual import"}
                    </Badge>
                    {c.kind === "real" && !c.enabled && (
                      <Badge variant="outline">Not configured</Badge>
                    )}
                  </div>
                  <p className="text-muted-foreground">{c.note}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
