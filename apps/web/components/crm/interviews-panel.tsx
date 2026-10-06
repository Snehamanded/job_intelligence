"use client";

import { Trash2 } from "lucide-react";

import { InterviewForm } from "@/components/crm/interview-form";
import { Button } from "@/components/ui/button";
import type { ApplicationDetail, Interview } from "@/lib/api/client";
import { useAddInterview, useDeleteInterview, useUpdateInterview } from "@/lib/api/crm";
import { KIND_LABEL, formatDateTime } from "@/lib/crm";

const OUTCOMES: Interview["outcome"][] = ["pending", "passed", "failed", "cancelled"];

export function InterviewsPanel({ application }: { application: ApplicationDetail }) {
  const add = useAddInterview(application.id);
  const update = useUpdateInterview(application.id);
  const remove = useDeleteInterview(application.id);

  return (
    <div className="grid gap-4">
      <ul className="grid gap-3">
        {application.interviews.map((iv) => (
          <li key={iv.id} className="grid gap-2 rounded-lg border p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{KIND_LABEL[iv.kind]}</span>
              <span className="text-muted-foreground">{formatDateTime(iv.scheduled_at)}</span>
              <select
                aria-label="Outcome"
                value={iv.outcome}
                onChange={(e) =>
                  update.mutate({ id: iv.id, outcome: e.target.value as Interview["outcome"] })
                }
                className="ml-auto h-7 rounded-md border bg-background px-1 text-xs capitalize"
              >
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label="Delete interview"
                onClick={() => remove.mutate(iv.id)}
              >
                <Trash2 />
              </Button>
            </div>
            {iv.location && <p className="break-all text-muted-foreground">{iv.location}</p>}
            {iv.checklist.length > 0 && (
              <ul className="grid gap-1" aria-label="Preparation checklist">
                {iv.checklist.map((item, i) => (
                  <li key={i}>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={item.done ?? false}
                        onChange={() =>
                          update.mutate({
                            id: iv.id,
                            checklist: iv.checklist.map((c, j) =>
                              j === i ? { ...c, done: !c.done } : c,
                            ),
                          })
                        }
                      />
                      <span className={item.done ? "text-muted-foreground line-through" : ""}>
                        {item.text}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
        {application.interviews.length === 0 && (
          <li className="text-sm text-muted-foreground">No interviews yet.</li>
        )}
      </ul>
      <InterviewForm onSubmit={(body) => add.mutateAsync(body)} error={add.error?.message} />
    </div>
  );
}
