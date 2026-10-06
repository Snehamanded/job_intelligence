"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ScoringSettings } from "@/lib/api/client";

const WEIGHTS = [
  "skills",
  "experience",
  "role",
  "location",
  "projects",
  "industry",
  "preferences",
] as const;
const RANKING = [
  ["match", "Match score"],
  ["freshness", "Freshness"],
  ["salary_fit", "Salary fit"],
  ["user_priority", "Your priority"],
] as const;

type Weight = (typeof WEIGHTS)[number];

type Props = {
  initial: ScoringSettings;
  onSubmit: (settings: ScoringSettings) => Promise<unknown>;
  error?: string | null;
};

export function ScoringForm({ initial, onSubmit, error }: Props) {
  const [weights, setWeights] = useState(
    () =>
      Object.fromEntries(WEIGHTS.map((k) => [k, initial.weights?.[k] ?? 0])) as Record<
        Weight,
        number
      >,
  );
  const [ranking, setRanking] = useState(() =>
    Object.fromEntries(RANKING.map(([k]) => [k, Math.round((initial.ranking?.[k] ?? 0) * 100)])),
  );
  const [topN, setTopN] = useState(initial.llm_top_n ?? 10);
  const [problem, setProblem] = useState<string | null>(null);

  const rankingTotal = Object.values(ranking).reduce((a, b) => a + b, 0);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (rankingTotal !== 100) {
      setProblem(`Ranking percentages must add up to 100 (now ${rankingTotal}).`);
      return;
    }
    if (Object.values(weights).every((w) => !w)) {
      setProblem("At least one weight must be above zero.");
      return;
    }
    setProblem(null);
    try {
      await onSubmit({
        ...initial,
        weights,
        ranking: Object.fromEntries(
          Object.entries(ranking).map(([k, v]) => [k, v / 100]),
        ) as ScoringSettings["ranking"],
        llm_top_n: topN,
      });
    } catch {
      // Shown through `error`.
    }
  };

  const num = (value: number, set: (v: number) => void, id: string, max = 100) => (
    <Input
      id={id}
      type="number"
      min={0}
      max={max}
      value={value}
      onChange={(e) => set(Math.max(0, Math.min(max, Number(e.target.value) || 0)))}
      className="w-20"
    />
  );

  return (
    <form onSubmit={submit} noValidate className="grid gap-6">
      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-medium">Match score weights</legend>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {WEIGHTS.map((k) => (
            <div key={k} className="grid gap-1">
              <Label htmlFor={`w-${k}`} className="capitalize">
                {k}
              </Label>
              {num(weights[k], (v) => setWeights((w) => ({ ...w, [k]: v })), `w-${k}`)}
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Relative weights; they don&apos;t need to add up to 100.
        </p>
      </fieldset>
      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-medium">Ranking (%)</legend>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {RANKING.map(([k, label]) => (
            <div key={k} className="grid gap-1">
              <Label htmlFor={`r-${k}`}>{label}</Label>
              {num(ranking[k], (v) => setRanking((r) => ({ ...r, [k]: v })), `r-${k}`)}
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">Total: {rankingTotal}% (must be 100%).</p>
      </fieldset>
      <div className="grid gap-1">
        <Label htmlFor="top-n">Jobs reviewed by AI per scoring run</Label>
        {num(topN, setTopN, "top-n", 30)}
        <p className="text-xs text-muted-foreground">
          Only the best few eligible jobs are sent to the AI, to keep cost low. 0 turns this off.
        </p>
      </div>
      {(problem ?? error) && (
        <p role="alert" className="text-sm text-destructive">
          {problem ?? error}
        </p>
      )}
      <div>
        <Button type="submit">Save and rescore</Button>
      </div>
    </form>
  );
}
