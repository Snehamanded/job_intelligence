"use client";

import { BarChart3 } from "lucide-react";

import { FunnelChart, RatesTable, WeeklyChart } from "@/components/crm/charts";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAnalytics } from "@/lib/api/crm";
import { percent } from "@/lib/crm";
import { SOURCE_LABEL } from "@/lib/jobs-format";

export default function AnalyticsPage() {
  const analytics = useAnalytics();
  const data = analytics.data;

  return (
    <>
      <PageHeader
        title="Analytics"
        description="What's working: rates are out of applications you actually sent."
      />
      {!data ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data.funnel.saved === 0 ? (
        <EmptyState icon={BarChart3} title="No applications yet">
          Track a few applications and your funnel and response rates appear here.
        </EmptyState>
      ) : (
        <div className="grid gap-6">
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ["Applied", String(data.overall.applied)],
              ["Response rate", percent(data.overall.response_rate)],
              ["Interview rate", percent(data.overall.interview_rate)],
              ["Offer rate", percent(data.overall.offer_rate)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border bg-card p-4">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="mt-1 text-2xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Funnel</CardTitle>
                <CardDescription>Applications that ever reached each stage.</CardDescription>
              </CardHeader>
              <CardContent>
                <FunnelChart funnel={data.funnel} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Applications per week</CardTitle>
                <CardDescription>By the date you applied, last 12 weeks.</CardDescription>
              </CardHeader>
              <CardContent>
                <WeeklyChart weekly={data.weekly} />
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>By source</CardTitle>
            </CardHeader>
            <CardContent>
              <RatesTable
                caption="Rates by source"
                rows={data.by_source}
                labels={{ ...SOURCE_LABEL, external: "Applied elsewhere" }}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>By match level</CardTitle>
              <CardDescription>Do higher-match jobs actually respond more?</CardDescription>
            </CardHeader>
            <CardContent>
              <RatesTable caption="Rates by match level" rows={data.by_match_band} />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
