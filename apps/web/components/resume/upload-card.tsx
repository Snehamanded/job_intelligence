"use client";

import { Upload } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ACCEPTED_EXTENSIONS, validateResumeFile } from "@/lib/resume-file";
import { cn } from "@/lib/utils";

type Props = {
  onUpload: (file: File) => Promise<unknown>;
  uploading?: boolean;
  serverError?: string | null;
};

export function UploadCard({ onUpload, uploading = false, serverError }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const submit = async (file: File | undefined) => {
    if (!file) return;
    const problem = validateResumeFile(file);
    setError(problem);
    if (problem) return;
    try {
      await onUpload(file);
    } catch {
      // Shown through serverError.
    }
    if (input.current) input.current.value = "";
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void submit(event.dataTransfer.files[0]);
  };

  const message = error ?? serverError;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload resume</CardTitle>
        <CardDescription>
          PDF, DOCX or TXT, up to 5 MB. Each upload creates a new profile version.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-8 text-center transition-colors",
            dragging && "border-primary bg-accent",
          )}
        >
          <Upload className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Drag a file here, or</p>
          <Button type="button" onClick={() => input.current?.click()} disabled={uploading}>
            {uploading ? "Uploading…" : "Choose file"}
          </Button>
          <input
            ref={input}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="sr-only"
            aria-label="Resume file"
            onChange={(e) => void submit(e.target.files?.[0])}
          />
        </div>
        {message && (
          <p role="alert" className="text-sm text-destructive">
            {message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
