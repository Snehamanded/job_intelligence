"use client";

import { useState } from "react";

import { ApplicationCard } from "@/components/crm/application-card";
import type { Application, Stage } from "@/lib/api/client";
import { STAGES } from "@/lib/crm";
import { cn } from "@/lib/utils";

type Props = {
  applications: Application[];
  onMove: (id: string, stage: Stage) => void;
};

/** Kanban board. Drag a card between columns, or use the stage menu on each card. */
export function Board({ applications, onMove }: Props) {
  const [over, setOver] = useState<Stage | null>(null);
  return (
    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
      {STAGES.map(({ value, label }) => {
        const items = applications.filter((a) => a.stage === value);
        return (
          <section
            key={value}
            aria-label={label}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(value);
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(null);
              const id = e.dataTransfer.getData("text/application-id");
              const current = applications.find((a) => a.id === id);
              if (id && current && current.stage !== value) onMove(id, value);
            }}
            className={cn(
              "grid min-h-40 min-w-0 content-start gap-2 rounded-xl border bg-muted/40 p-2 transition-colors",
              over === value && "border-primary bg-accent",
            )}
          >
            <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
              {label}
              <span className="text-xs font-normal text-muted-foreground">{items.length}</span>
            </h2>
            {items.map((a) => (
              <ApplicationCard key={a.id} application={a} onMove={(stage) => onMove(a.id, stage)} />
            ))}
          </section>
        );
      })}
    </div>
  );
}
