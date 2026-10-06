import { Construction } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

export function ComingSoon({
  title,
  phase,
  summary,
}: {
  title: string;
  phase: number;
  summary: string;
}) {
  return (
    <>
      <PageHeader title={title} description={summary} />
      <EmptyState icon={Construction} title={`Coming in Phase ${phase}`}>
        This section is planned but not built yet.
      </EmptyState>
    </>
  );
}
