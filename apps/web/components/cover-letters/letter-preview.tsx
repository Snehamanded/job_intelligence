export function LetterPreview({
  company,
  paragraphs,
  signature,
}: {
  company: string;
  paragraphs: string[];
  signature: string | null | undefined;
}) {
  return (
    <article className="grid gap-3 text-sm leading-relaxed" aria-label="Letter preview">
      <p>Dear Hiring Team at {company},</p>
      {paragraphs.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      {paragraphs.length === 0 && (
        <p className="text-muted-foreground">No sentences included yet.</p>
      )}
      <p>
        Sincerely,
        {signature && (
          <>
            <br />
            {signature}
          </>
        )}
      </p>
    </article>
  );
}
