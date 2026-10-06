"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AnalyticsData, GroupRates } from "@/lib/api/client";
import { STAGE_LABEL, percent } from "@/lib/crm";

// Single-series charts: one hue (primary), recessive grid and axes, text in ink tokens.
const BAR = "var(--color-primary)";
const GRID = "var(--color-border)";
const TICK = { fill: "var(--color-muted-foreground)", fontSize: 12 };
const TOOLTIP = {
  contentStyle: {
    background: "var(--color-popover)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    fontSize: 12,
    color: "var(--color-foreground)",
  },
  cursor: { fill: "var(--color-accent)" },
};

function TableView({ caption, rows }: { caption: string; rows: [string, string | number][] }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-xs text-muted-foreground">Show as table</summary>
      <table className="mt-2 w-full text-left">
        <caption className="sr-only">{caption}</caption>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b last:border-0">
              <th scope="row" className="py-1 font-normal text-muted-foreground">
                {k}
              </th>
              <td className="py-1 text-right tabular-nums">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export function FunnelChart({ funnel }: { funnel: AnalyticsData["funnel"] }) {
  const data = (["saved", "applied", "interviewing", "offer"] as const).map((stage) => ({
    label: STAGE_LABEL[stage],
    count: funnel[stage] ?? 0,
  }));
  return (
    <div className="grid gap-2">
      <div className="h-52" role="img" aria-label="Applications that reached each stage">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 8, right: 32, top: 4, bottom: 4 }}
          >
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={TICK}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={92}
              tick={TICK}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip {...TOOLTIP} formatter={(v) => [v, "Applications"]} />
            <Bar
              dataKey="count"
              fill={BAR}
              radius={[0, 4, 4, 0]}
              barSize={18}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="count"
                position="right"
                style={{ fill: "var(--color-foreground)", fontSize: 12 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView caption="Funnel" rows={data.map((d) => [d.label, d.count])} />
    </div>
  );
}

export function WeeklyChart({ weekly }: { weekly: AnalyticsData["weekly"] }) {
  const data = weekly.map((w) => ({
    label: new Date(`${w.week_start}T00:00:00`).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
    }),
    applied: w.applied,
  }));
  return (
    <div className="grid gap-2">
      <div className="h-52" role="img" aria-label="Applications per week, last 12 weeks">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tick={TICK} axisLine={false} tickLine={false} interval={1} />
            <YAxis allowDecimals={false} tick={TICK} axisLine={false} tickLine={false} width={28} />
            <Tooltip
              {...TOOLTIP}
              formatter={(v) => [v, "Applied"]}
              labelFormatter={(l) => `Week of ${l}`}
            />
            <Bar
              dataKey="applied"
              fill={BAR}
              radius={[4, 4, 0, 0]}
              maxBarSize={22}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption="Applications per week"
        rows={data.map((d) => [`Week of ${d.label}`, d.applied])}
      />
    </div>
  );
}

function RateCell({ rate }: { rate: number | null | undefined }) {
  return (
    <td className="py-2 pl-3">
      <div className="flex items-center justify-end gap-2">
        <div
          className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-primary/15 sm:block"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={rate == null ? undefined : Math.round(rate * 100)}
          aria-label="rate"
        >
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${(rate ?? 0) * 100}%` }}
          />
        </div>
        <span className="w-10 text-right tabular-nums">{percent(rate)}</span>
      </div>
    </td>
  );
}

/** Rates by group as a table with single-hue meters (more readable than a multi-colour chart). */
export function RatesTable({
  caption,
  rows,
  labels = {},
}: {
  caption: string;
  rows: GroupRates[];
  labels?: Record<string, string>;
}) {
  if (rows.length === 0)
    return <p className="text-sm text-muted-foreground">No applications yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th scope="col" className="py-2 text-left font-medium">
              Group
            </th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">
              Applied
            </th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">
              Response
            </th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">
              Interview
            </th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">
              Offer
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.group} className="border-b last:border-0">
              <th scope="row" className="py-2 text-left font-medium">
                {labels[r.group] ?? r.group}
              </th>
              <td className="py-2 pl-3 text-right tabular-nums">{r.applied}</td>
              <RateCell rate={r.response_rate} />
              <RateCell rate={r.interview_rate} />
              <RateCell rate={r.offer_rate} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
