"use client";

import { useParams } from "next/navigation";

import { AuthGuard } from "@/components/auth-guard";
import { LetterPreview } from "@/components/cover-letters/letter-preview";
import { Button } from "@/components/ui/button";
import { useCoverLetter } from "@/lib/api/cover-letters";

function PrintableLetter() {
  const { id } = useParams<{ id: string }>();
  const letter = useCoverLetter(id);
  if (!letter.data) return <p className="p-8 text-sm">Loading…</p>;
  if (letter.data.status !== "saved")
    return <p className="p-8 text-sm">Save this letter before printing it.</p>;
  return (
    <main className="mx-auto max-w-[760px] bg-white p-10 text-black print:p-[16mm]">
      <div className="mb-6 flex items-center gap-3 print:hidden">
        <Button onClick={() => window.print()}>Print / Save as PDF</Button>
        <span className="text-sm text-muted-foreground">
          Choose “Save as PDF” as the destination.
        </span>
      </div>
      <LetterPreview
        company={letter.data.company}
        paragraphs={letter.data.preview}
        signature={letter.data.signature}
      />
    </main>
  );
}

export default function PrintPage() {
  return (
    <AuthGuard>
      <PrintableLetter />
    </AuthGuard>
  );
}
