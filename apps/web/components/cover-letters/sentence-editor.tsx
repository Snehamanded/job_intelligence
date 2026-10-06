"use client";

import { AlertTriangle, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { LetterParagraph, LetterSentence } from "@/lib/api/client";
import type { SentenceEdits } from "@/lib/api/cover-letters";
import { cn } from "@/lib/utils";

const KIND_LABEL = {
  claim: "About you",
  company: "About the company",
  connective: "Connecting text",
};

function SourceBadge({ sentence }: { sentence: LetterSentence }) {
  if (sentence.source === "user") return <Badge variant="outline">Your words</Badge>;
  return (
    <Badge variant="secondary">
      {sentence.source === "ai" ? "AI" : "Template"} · {KIND_LABEL[sentence.kind]}
    </Badge>
  );
}

function SentenceRow({
  sentence,
  onEdit,
  readOnly,
  busy,
}: {
  sentence: LetterSentence;
  onEdit: (edits: SentenceEdits) => void;
  readOnly: boolean;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sentence.text);
  const unsupported = sentence.status === "unsupported";
  const included = sentence.included ?? true;

  return (
    <li
      className={cn(
        "grid gap-1.5 rounded-md border p-2 text-sm",
        unsupported && "border-destructive/40 bg-destructive/5",
        !unsupported && !included && "opacity-60",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        {!readOnly && (
          <input
            type="checkbox"
            aria-label={`Include: ${sentence.text}`}
            checked={included && !unsupported}
            disabled={unsupported || busy}
            onChange={(e) => onEdit({ updates: { [sentence.id]: { included: e.target.checked } } })}
          />
        )}
        <SourceBadge sentence={sentence} />
        {unsupported && <Badge variant="destructive">Unsupported</Badge>}
        {!readOnly && !editing && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-7"
            onClick={() => {
              setDraft(sentence.text);
              setEditing(true);
            }}
            aria-label={`Edit: ${sentence.text}`}
          >
            <Pencil /> Edit
          </Button>
        )}
      </div>
      {editing ? (
        <form
          className="grid gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) onEdit({ updates: { [sentence.id]: { text: draft.trim() } } });
            setEditing(false);
          }}
        >
          <textarea
            aria-label="Sentence text"
            value={draft}
            maxLength={600}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-16 rounded-md border bg-transparent px-2 py-1"
          />
          <p className="text-xs text-muted-foreground">
            Edited sentences become your own words: they&apos;re labeled that way and not
            machine-checked.
          </p>
          <div className="flex gap-2">
            <Button size="sm" type="submit">
              Use my wording
            </Button>
            <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <p className={cn(unsupported && "text-muted-foreground line-through")}>{sentence.text}</p>
      )}
      {sentence.kind === "company" &&
        sentence.job_quote &&
        !unsupported &&
        sentence.source !== "user" && (
          <p className="text-xs text-muted-foreground">From the posting: “{sentence.job_quote}”</p>
        )}
      {unsupported && (
        <ul className="grid gap-0.5 text-xs text-destructive" aria-label="Problems">
          {(sentence.issues ?? []).map((issue, i) => (
            <li key={i} className="flex items-start gap-1">
              <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden /> {issue}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function SentenceEditor({
  paragraphs,
  onEdit,
  readOnly = false,
  busy = false,
}: {
  paragraphs: LetterParagraph[];
  onEdit: (edits: SentenceEdits) => void;
  readOnly?: boolean;
  busy?: boolean;
}) {
  const [adding, setAdding] = useState<Record<string, string>>({});
  return (
    <div className="grid gap-5">
      {paragraphs.map((p, i) => (
        <section key={p.id} aria-label={`Paragraph ${i + 1}`} className="grid gap-2">
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Paragraph {i + 1}
          </h3>
          <ul className="grid gap-2">
            {(p.sentences ?? []).map((s) => (
              <SentenceRow
                key={s.id}
                sentence={s}
                onEdit={onEdit}
                readOnly={readOnly}
                busy={busy}
              />
            ))}
          </ul>
          {!readOnly && (
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const text = (adding[p.id] ?? "").trim();
                if (!text) return;
                onEdit({ add: [{ paragraph_id: p.id, text }] });
                setAdding({ ...adding, [p.id]: "" });
              }}
            >
              <input
                aria-label={`Add your own sentence to paragraph ${i + 1}`}
                placeholder="Add a sentence in your own words"
                value={adding[p.id] ?? ""}
                maxLength={600}
                onChange={(e) => setAdding({ ...adding, [p.id]: e.target.value })}
                className="h-8 flex-1 rounded-md border bg-transparent px-2 text-sm"
              />
              <Button size="sm" variant="outline" type="submit">
                <Plus /> Add
              </Button>
            </form>
          )}
        </section>
      ))}
    </div>
  );
}
