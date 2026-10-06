"use client";

import { Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAddJobSource, useConnectors, useDeleteJobSource, useJobSources } from "@/lib/api/jobs";

export default function SourcesPage() {
  const sources = useJobSources();
  const connectors = useConnectors();
  const add = useAddJobSource();
  const remove = useDeleteJobSource();
  const [token, setToken] = useState("");

  const onAdd = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(token, { onSuccess: () => setToken("") });
  };

  return (
    <>
      <PageHeader title="Job sources" description="Where searches look for jobs." />
      <div className="grid max-w-3xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Greenhouse boards</CardTitle>
            <CardDescription>
              Many companies post jobs on Greenhouse. Add a company&apos;s board token: the part
              after <code>greenhouse.io/</code> in its careers link (e.g. <code>gitlab</code>).
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <form onSubmit={onAdd} className="flex max-w-md items-end gap-2">
              <div className="grid flex-1 gap-2">
                <Label htmlFor="board">Board token</Label>
                <Input
                  id="board"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="gitlab"
                />
              </div>
              <Button type="submit" disabled={!token.trim() || add.isPending}>
                {add.isPending ? "Checking…" : "Add board"}
              </Button>
            </form>
            {add.error && (
              <p role="alert" className="text-sm text-destructive">
                {add.error.message}
              </p>
            )}
            <ul className="divide-y" aria-label="Boards">
              {(sources.data ?? []).map((s) => (
                <li key={s.id} className="flex items-center gap-3 py-2 text-sm">
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
              {sources.data?.length === 0 && (
                <li className="py-2 text-sm text-muted-foreground">No boards added yet.</li>
              )}
            </ul>
          </CardContent>
        </Card>

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
                    {c.kind === "mock" && c.enabled && (
                      <Badge variant="warning">mock enabled</Badge>
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
