"use client";

import { KanbanSquare } from "lucide-react";
import Link from "next/link";

import { Board } from "@/components/crm/board";
import { ExternalApplicationForm } from "@/components/crm/external-form";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApplications, useCreateApplication, useUpdateApplication } from "@/lib/api/crm";

export default function ApplicationsPage() {
  const applications = useApplications();
  const update = useUpdateApplication();
  const create = useCreateApplication();

  return (
    <>
      <PageHeader
        title="Applications"
        description="Drag cards between columns, or use the stage menu on each card. You apply on the employer's site; this is your tracker."
      />
      <div className="grid gap-6">
        {update.error && (
          <p role="alert" className="text-sm text-destructive">
            {update.error.message}
          </p>
        )}
        {applications.data && applications.data.length === 0 ? (
          <EmptyState icon={KanbanSquare} title="Nothing tracked yet">
            Open a job and choose <strong>Save</strong> or <strong>I applied</strong>, or add a job
            you applied to elsewhere below.{" "}
            <Link href="/jobs" className="text-primary underline">
              Browse jobs
            </Link>
          </EmptyState>
        ) : (
          <Board
            applications={applications.data ?? []}
            onMove={(id, stage) => update.mutate({ id, stage })}
          />
        )}
        <Card>
          <CardHeader>
            <CardTitle>Track a job applied to elsewhere</CardTitle>
            <CardDescription>For jobs that aren&apos;t in your job list.</CardDescription>
          </CardHeader>
          <CardContent>
            <ExternalApplicationForm
              onSubmit={(body) => create.mutateAsync(body)}
              error={create.error?.message}
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
