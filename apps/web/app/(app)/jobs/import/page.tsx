"use client";

import { useRouter } from "next/navigation";

import { BulkImportForm } from "@/components/jobs/bulk-import-form";
import { ImportForm } from "@/components/jobs/import-form";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useImportJob } from "@/lib/api/jobs";

export default function ImportJobPage() {
  const router = useRouter();
  const importJob = useImportJob();
  return (
    <>
      <PageHeader
        title="Import jobs"
        description="Add a job you found anywhere. It's checked against your preferences like any other."
      />
      <Card className="mb-6 max-w-3xl">
        <CardHeader>
          <CardTitle>Many jobs at once</CardTitle>
          <CardDescription>
            Paste job alert emails or WhatsApp job messages. Each job post is found and added. Links
            to company career pages are read in full; LinkedIn, Naukri and similar links are kept
            for you to open, never fetched.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BulkImportForm />
        </CardContent>
      </Card>
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>One job</CardTitle>
        </CardHeader>
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
