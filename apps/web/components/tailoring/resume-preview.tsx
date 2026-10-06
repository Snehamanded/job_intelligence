import type { ResumeDocument } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/** Single-column resume. `highlight` marks AI-reworded bullets (editor only, never in print). */
export function ResumePreview({
  doc,
  highlight = false,
}: {
  doc: ResumeDocument;
  highlight?: boolean;
}) {
  const c = doc.contact ?? {};
  const contact = [c.email, c.phone, c.location, ...(c.links ?? [])].filter(Boolean).join(" | ");
  const section = "mt-4 border-b pb-1 text-sm font-semibold tracking-wide uppercase";
  return (
    <article className="resume grid text-sm leading-relaxed" aria-label="Resume preview">
      {c.name && <h1 className="text-xl font-semibold">{c.name}</h1>}
      {contact && <p className="text-muted-foreground">{contact}</p>}
      {(doc.summary ?? []).length > 0 && (
        <>
          <h2 className={section}>Summary</h2>
          <p className="mt-1">{doc.summary!.map((s) => s.text).join(" ")}</p>
        </>
      )}
      {(doc.skills ?? []).length > 0 && (
        <>
          <h2 className={section}>Skills</h2>
          <p className="mt-1">{doc.skills!.map((s) => s.name).join(", ")}</p>
        </>
      )}
      {(doc.experience ?? []).length > 0 && (
        <>
          <h2 className={section}>Experience</h2>
          {doc.experience!.map((role) => (
            <section key={role.id} className="mt-2">
              <p>
                <strong>
                  {role.title}, {role.company}
                </strong>
                {[role.location, role.date_text].filter(Boolean).length > 0 && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {[role.location, role.date_text].filter(Boolean).join(" · ")}
                  </span>
                )}
              </p>
              <ul className="list-disc pl-5">
                {(role.bullets ?? []).map((b) => (
                  <li
                    key={b.id}
                    className={cn(highlight && b.ai_changed && "rounded bg-primary/10")}
                    title={
                      highlight && b.ai_changed
                        ? `AI-reworded. Original: ${b.original_text}`
                        : undefined
                    }
                  >
                    {b.text}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
      {(doc.projects ?? []).length > 0 && (
        <>
          <h2 className={section}>Projects</h2>
          {doc.projects!.map((p) => (
            <p key={p.id} className="mt-1">
              <strong>{p.name}</strong>
              {p.description ? `: ${p.description}` : ""}
              {(p.technologies ?? []).length > 0 && (
                <span className="text-muted-foreground"> ({p.technologies!.join(", ")})</span>
              )}
            </p>
          ))}
        </>
      )}
      {(doc.education ?? []).length > 0 && (
        <>
          <h2 className={section}>Education</h2>
          {doc.education!.map((e, i) => (
            <p key={i} className="mt-1">
              {[
                e.institution,
                e.degree,
                // Skip the field when the degree already names it ("B.E. in Computer Science").
                e.field_of_study && e.degree?.toLowerCase().includes(e.field_of_study.toLowerCase())
                  ? null
                  : e.field_of_study,
                e.date_text,
              ]
                .filter(Boolean)
                .join(", ")}
            </p>
          ))}
        </>
      )}
      {(doc.certifications ?? []).length > 0 && (
        <>
          <h2 className={section}>Certifications</h2>
          <ul className="list-disc pl-5">
            {doc.certifications!.map((cert, i) => (
              <li key={i}>
                {cert.name}
                {cert.issuer ? ` (${cert.issuer})` : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
