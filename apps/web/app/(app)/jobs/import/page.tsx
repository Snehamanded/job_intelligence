"use client";

import { useRouter } from "next/navigation";

import { ImportForm } from "@/components/jobs/import-form";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { useImportJob } from "@/lib/api/jobs";

export default function ImportJobPage() {
  const router = useRouter();
  const importJob = useImportJob();
  return (
    <>
      <PageHeader
        title="Import a job"
        description="Add a job you found anywhere. It's checked against your preferences like any other."
      />
      <Card className="max-w-3xl">
        <CardContent>
          <ImportForm
            pending={importJob.isPending}
            error={importJob.error?.message}
            onImport={(body) =>
              importJob.mutateAsync(body).then((job) => router.push(`/jobs/${job.id}`))
            }
          />
        </CardContent>
      </Card>
    </>
  );
}
