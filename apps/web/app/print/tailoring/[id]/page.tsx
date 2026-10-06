"use client";

import { useParams } from "next/navigation";

import { AuthGuard } from "@/components/auth-guard";
import { ResumePreview } from "@/components/tailoring/resume-preview";
import { Button } from "@/components/ui/button";
import { useTailoring } from "@/lib/api/tailoring";

/** A clean, single-column page for printing or "Save as PDF". No app chrome, no highlights. */
function PrintableResume() {
  const { id } = useParams<{ id: string }>();
  const version = useTailoring(id);
  if (!version.data?.preview) return <p className="p-8 text-sm">Loading…</p>;
  if (version.data.status !== "saved")
    return <p className="p-8 text-sm">Save this version before printing it.</p>;
  return (
    <main className="mx-auto max-w-[800px] bg-white p-10 text-black print:p-0">
      <div className="mb-6 flex items-center gap-3 print:hidden">
        <Button onClick={() => window.print()}>Print / Save as PDF</Button>
        <span className="text-sm text-muted-foreground">
          Choose “Save as PDF” as the destination.
        </span>
      </div>
      <ResumePreview doc={version.data.preview} />
    </main>
  );
}

export default function PrintPage() {
  return (
    <AuthGuard>
      <PrintableResume />
    </AuthGuard>
  );
}
