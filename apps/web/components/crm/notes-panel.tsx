"use client";

import { Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import type { ApplicationDetail } from "@/lib/api/client";
import { useAddNote, useDeleteNote } from "@/lib/api/crm";

export function NotesPanel({ application }: { application: ApplicationDetail }) {
  const add = useAddNote(application.id);
  const remove = useDeleteNote(application.id);
  const [body, setBody] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!body.trim()) return;
    add.mutate(body, { onSuccess: () => setBody("") });
  };

  return (
    <div className="grid gap-4">
      <form onSubmit={submit} className="grid gap-2">
        <label htmlFor="note" className="sr-only">
          New note
        </label>
        <textarea
          id="note"
          value={body}
          maxLength={5000}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Recruiter call, referral, salary discussed…"
          className="min-h-20 rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
        <div>
          <Button type="submit" size="sm" disabled={!body.trim() || add.isPending}>
            Add note
          </Button>
        </div>
      </form>
      <ul className="grid gap-3">
        {application.notes.map((note) => (
          <li key={note.id} className="grid gap-1 rounded-lg border p-3 text-sm">
            <div className="flex items-center text-xs text-muted-foreground">
              {new Date(note.created_at).toLocaleString()}
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto size-7"
                aria-label="Delete note"
                onClick={() => remove.mutate(note.id)}
              >
                <Trash2 />
              </Button>
            </div>
            <p className="whitespace-pre-line">{note.body}</p>
          </li>
        ))}
        {application.notes.length === 0 && (
          <li className="text-sm text-muted-foreground">No notes yet.</li>
        )}
      </ul>
    </div>
  );
}
