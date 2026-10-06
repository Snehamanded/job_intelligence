"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useCreateCoverLetter, type NewCoverLetter } from "@/lib/api/cover-letters";
import { useJob } from "@/lib/api/jobs";
import { useTailoringList } from "@/lib/api/tailoring";

function NewLetter({ jobId }: { jobId: string }) {
  const router = useRouter();
  const job = useJob(jobId);
  const versions = useTailoringList(jobId);
  const create = useCreateCoverLetter();
  const [tone, setTone] = useState<NewCoverLetter["tone"]>("professional");
  const [length, setLength] = useState<NewCoverLetter["length"]>("medium");
  const [base, setBase] = useState("");
  const saved = (versions.data ?? []).filter((v) => v.status === "saved");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { job_id: jobId, tone, length, resume_version_id: base || null },
      { onSuccess: (letter) => router.replace(`/cover-letters/${letter.id}`) },
    );
  };

  const select = "h-9 rounded-md border bg-background px-2 text-sm";
  return (
    <>
      <PageHeader
        title="Write a cover letter"
        description={job.data ? `For ${job.data.title} at ${job.data.company}` : undefined}
      />
      <Card className="max-w-xl">
        <CardContent>
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-1">
              <Label htmlFor="tone">Tone</Label>
              <select
                id="tone"
                value={tone}
                onChange={(e) => setTone(e.target.value as NewCoverLetter["tone"])}
                className={select}
              >
                <option value="professional">Professional</option>
                <option value="warm">Warm</option>
                <option value="concise">Concise</option>
              </select>
            </div>
            <div className="grid gap-1">
              <Label htmlFor="length">Length</Label>
              <select
                id="length"
                value={length}
                onChange={(e) => setLength(e.target.value as NewCoverLetter["length"])}
                className={select}
              >
                <option value="short">Short (about 150 words)</option>
                <option value="medium">Medium (about 250 words)</option>
              </select>
            </div>
            <div className="grid gap-1">
              <Label htmlFor="base">Based on</Label>
              <select
                id="base"
                value={base}
                onChange={(e) => setBase(e.target.value)}
                className={select}
              >
                <option value="">My verified resume</option>
                {saved.map((v) => (
                  <option key={v.id} value={v.id}>
                    Tailored v{v.version}: {v.name}
                  </option>
                ))}
              </select>
            </div>
            {create.error && (
              <p role="alert" className="text-sm text-destructive">
                {create.error.message}
              </p>
            )}
            <div>
              <Button type="submit" disabled={create.isPending}>
                Write draft
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}

function NewLetterPage() {
  const jobId = useSearchParams().get("job");
  if (!jobId) return <p className="text-sm">Open a job and choose “Write cover letter”.</p>;
  return <NewLetter jobId={jobId} />;
}

export default function Page() {
  return (
    <Suspense>
      <NewLetterPage />
    </Suspense>
  );
}
