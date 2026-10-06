"use client";

import { PenLine } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useStartTailoring } from "@/lib/api/tailoring";

export function TailorButton({ jobId }: { jobId: string }) {
  const router = useRouter();
  const start = useStartTailoring();
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        disabled={start.isPending}
        onClick={() => start.mutate(jobId, { onSuccess: (v) => router.push(`/tailoring/${v.id}`) })}
      >
        <PenLine /> Tailor resume
      </Button>
      {start.error && <span className="text-sm text-destructive">{start.error.message}</span>}
    </span>
  );
}
