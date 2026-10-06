"use client";

import { Download, Search, Settings2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/empty-state";
import { JobCard } from "@/components/jobs/job-card";
import { SearchStatus } from "@/components/jobs/search-status";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  useJobs,
  useLatestSearch,
  useMatchStatus,
  useRescore,
  useStartSearch,
} from "@/lib/api/jobs";
import { useProfile } from "@/lib/api/profile";
import { SOURCE_LABEL } from "@/lib/jobs-format";

const PAGE = 30;

export default function JobsPage() {
  const profile = useProfile();
  const latest = useLatestSearch();
  const startSearch = useStartSearch();
  const [keywords, setKeywords] = useState<string | null>(null);
  const [eligibleOnly, setEligibleOnly] = useState(true);
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const [sort, setSort] = useState<"rank" | "newest">("rank");
  const jobs = useJobs({ eligibleOnly, source, q, limit, sort });
  const matchStatus = useMatchStatus();
  const rescore = useRescore();
  const scoring =
    matchStatus.data != null &&
    matchStatus.data.profile_version != null &&
    matchStatus.data.scored_jobs < matchStatus.data.total_jobs;

  const targetRoles = (profile.data?.preferences.target_roles ?? []).join(", ");
  const running = latest.data?.status === "queued" || latest.data?.status === "running";

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    const list =
      keywords === null
        ? null
        : keywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean);
    startSearch.mutate(list);
  };

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Search your sources, then review jobs that fit your preferences."
      />
      <div className="grid gap-6">
        <Card>
          <CardContent className="grid gap-4">
            <form onSubmit={onSearch} className="flex flex-wrap items-end gap-3">
              <div className="grid min-w-64 flex-1 gap-2">
                <Label htmlFor="keywords">Job titles to look for</Label>
                <Input
                  id="keywords"
                  value={keywords ?? targetRoles}
                  onChange={(e) => setKeywords(e.target.value)}
                  placeholder="Backend Engineer, Python Developer (empty = all titles)"
                />
              </div>
              <Button type="submit" disabled={running || startSearch.isPending}>
                <Search /> {running ? "Searching…" : "Search"}
              </Button>
              <Button variant="outline" asChild>
                <Link href="/jobs/sources">
                  <Settings2 /> Sources
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/jobs/import">
                  <Download /> Import a job
                </Link>
              </Button>
            </form>
            {startSearch.error && (
              <p role="alert" className="text-sm text-destructive">
                {startSearch.error.message}
              </p>
            )}
            {latest.data && <SearchStatus run={latest.data} />}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="eligible-only"
              checked={eligibleOnly}
              onCheckedChange={(v) => {
                setEligibleOnly(v);
                setLimit(PAGE);
              }}
            />
            <Label htmlFor="eligible-only">Only jobs that fit my preferences</Label>
          </div>
          <select
            aria-label="Sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as "rank" | "newest")}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="rank">Best match</option>
            <option value="newest">Newest</option>
          </select>
          <select
            aria-label="Source"
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setLimit(PAGE);
            }}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            <option value="">All sources</option>
            {Object.entries(SOURCE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <Input
            aria-label="Filter by title or company"
            placeholder="Filter by title or company"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setLimit(PAGE);
            }}
            className="max-w-xs"
          />
        </div>

        {matchStatus.data && (
          <div
            className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground"
            aria-live="polite"
          >
            {scoring ? (
              <span>
                Scoring jobs… {matchStatus.data.scored_jobs} of {matchStatus.data.total_jobs}
              </span>
            ) : (
              matchStatus.data.total_jobs > 0 &&
              matchStatus.data.profile_version != null && (
                <span>
                  Scores are up to date
                  {matchStatus.data.ai_enabled ? " (with AI review of the top jobs)" : ""}.
                </span>
              )
            )}
            {matchStatus.data.note && (
              <span className="text-amber-700">{matchStatus.data.note}</span>
            )}
            {matchStatus.data.profile_version != null && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => rescore.mutate()}
                disabled={rescore.isPending}
              >
                Rescore
              </Button>
            )}
          </div>
        )}

        {jobs.data && (
          <p className="text-sm text-muted-foreground">
            {jobs.data.total} job{jobs.data.total === 1 ? "" : "s"}
            {eligibleOnly && jobs.data.hidden_ineligible > 0 && (
              <>
                {" "}
                · {jobs.data.hidden_ineligible} hidden because they don&apos;t fit your preferences{" "}
                <button
                  type="button"
                  className="text-primary underline-offset-4 hover:underline"
                  onClick={() => setEligibleOnly(false)}
                >
                  Show all
                </button>
              </>
            )}
          </p>
        )}

        {jobs.data && jobs.data.items.length === 0 ? (
          <EmptyState icon={Search} title="No jobs yet">
            Run a search: remote job boards and a starter set of company boards are searched for the
            roles in your profile. Add more companies under Sources, or import a job.
          </EmptyState>
        ) : (
          <div className="grid gap-3">
            {jobs.data?.items.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}
        {jobs.data && jobs.data.items.length < jobs.data.total && (
          <div>
            <Button variant="outline" onClick={() => setLimit((l) => l + PAGE)}>
              Show more
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
