import { Mail } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function WriteLetterButton({ jobId }: { jobId: string }) {
  return (
    <Button variant="outline" asChild>
      <Link href={`/cover-letters/new?job=${jobId}`}>
        <Mail /> Write cover letter
      </Link>
    </Button>
  );
}
