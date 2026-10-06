"use client";

import { AlertTriangle, Plus, Quote, Sparkles, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Profile, ProfileData } from "@/lib/api/client";
import { formatMonths } from "@/lib/resume-file";

type Props = {
  profile: Profile;
  onSave: (data: ProfileData) => Promise<unknown>;
  saving?: boolean;
  error?: string | null;
};

type Sourced = { source?: "resume" | "user"; evidence?: string | null };

function SourceHint({ item }: { item: Sourced }) {
  if (item.source === "user") {
    return <Badge variant="outline">Added by you</Badge>;
  }
  if (!item.evidence) return null;
  return (
    <span
      className="inline-flex cursor-help text-muted-foreground"
      title={`From your resume: “${item.evidence}”`}
      aria-label={`From your resume: ${item.evidence}`}
    >
      <Quote className="size-3" />
    </span>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Remove ${label}`}
      className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
    >
      <X className="size-3.5" />
    </button>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

const without = <T,>(list: T[], index: number) => list.filter((_, i) => i !== index);

export function ProfileReview({ profile, onSave, saving = false, error }: Props) {
  const [draft, setDraft] = useState<ProfileData>(profile.data);
  const [baseline, setBaseline] = useState(profile);
  const [newSkill, setNewSkill] = useState("");

  // Reset the draft when a new version arrives (re-parse or save).
  if (baseline.id !== profile.id) {
    setBaseline(profile);
    setDraft(profile.data);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(profile.data);
  const update = (patch: Partial<ProfileData>) => setDraft((d) => ({ ...d, ...patch }));
  const skills = draft.skills ?? [];
  const experience = draft.experience ?? [];
  const projects = draft.projects ?? [];
  const education = draft.education ?? [];
  const certifications = draft.certifications ?? [];
  const unsupported = draft.unsupported ?? [];

  const addSkill = (event: FormEvent) => {
    event.preventDefault();
    const name = newSkill.trim();
    if (!name || skills.some((s) => s.name.toLowerCase() === name.toLowerCase())) return;
    update({ skills: [...skills, { name, source: "user" }] });
    setNewSkill("");
  };

  const contact = draft.contact;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Your profile</CardTitle>
          <Badge variant="secondary">Version {profile.version}</Badge>
          {profile.parse_method === "llm" && (
            <Badge variant="success">
              <Sparkles /> Parsed with AI
            </Badge>
          )}
          {profile.parse_method === "heuristic" && <Badge variant="outline">Basic parsing</Badge>}
        </div>
        <CardDescription>
          Everything below comes from your resume. Hover <Quote className="inline size-3" /> to see
          the exact text. Remove anything that is wrong. Saving creates a new version.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6">
        <div className="grid gap-1 text-sm">
          {contact?.name && <p className="text-base font-semibold">{contact.name}</p>}
          <p className="text-muted-foreground">
            {[contact?.email, contact?.phone, contact?.location].filter(Boolean).join(" · ")}
          </p>
          <p>
            Total experience: <strong>{formatMonths(profile.experience_months)}</strong>
            <span className="text-muted-foreground"> (overlapping roles counted once)</span>
          </p>
        </div>

        <Section title={`Skills (${skills.length})`}>
          {skills.length === 0 && (
            <p className="text-sm text-muted-foreground">No skills found yet.</p>
          )}
          <ul className="flex flex-wrap gap-2" aria-label="Skills">
            {skills.map((skill, i) => (
              <li
                key={`${skill.name}-${i}`}
                className="flex items-center gap-1.5 rounded-md border bg-muted/40 py-1 pr-1 pl-2.5 text-sm"
              >
                {skill.name}
                <SourceHint item={skill} />
                <RemoveButton
                  label={skill.name}
                  onClick={() => update({ skills: without(skills, i) })}
                />
              </li>
            ))}
          </ul>
          <form onSubmit={addSkill} className="flex max-w-sm gap-2">
            <Input
              value={newSkill}
              onChange={(e) => setNewSkill(e.target.value)}
              placeholder="Add a skill you have"
              aria-label="New skill"
              maxLength={100}
            />
            <Button type="submit" variant="outline" disabled={!newSkill.trim()}>
              <Plus /> Add
            </Button>
          </form>
        </Section>

        <Section title="Experience">
          {experience.length === 0 && (
            <p className="text-sm text-muted-foreground">No roles found.</p>
          )}
          {experience.map((role, i) => (
            <div key={`${role.title}-${i}`} className="rounded-lg border p-3">
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    {role.title} · {role.company} <SourceHint item={role} />
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {role.date_text ?? "Dates not found"}
                    {role.location ? ` · ${role.location}` : ""}
                  </p>
                </div>
                <RemoveButton
                  label={`${role.title} at ${role.company}`}
                  onClick={() => update({ experience: without(experience, i) })}
                />
              </div>
              {(role.bullets ?? []).length > 0 && (
                <ul className="mt-2 grid gap-1">
                  {(role.bullets ?? []).map((bullet, j) => (
                    <li key={j} className="flex items-start gap-2 text-sm">
                      <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground" />
                      <span className="flex-1">{bullet.text}</span>
                      <RemoveButton
                        label={bullet.text}
                        onClick={() =>
                          update({
                            experience: experience.map((r, k) =>
                              k === i ? { ...r, bullets: without(r.bullets ?? [], j) } : r,
                            ),
                          })
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </Section>

        {projects.length > 0 && (
          <Section title="Projects">
            {projects.map((project, i) => (
              <div key={`${project.name}-${i}`} className="flex items-start gap-2 text-sm">
                <div className="flex-1">
                  <p className="font-medium">
                    {project.name} <SourceHint item={project} />
                  </p>
                  {project.description && (
                    <p className="text-muted-foreground">{project.description}</p>
                  )}
                  {(project.technologies ?? []).length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      {(project.technologies ?? []).join(", ")}
                    </p>
                  )}
                </div>
                <RemoveButton
                  label={project.name}
                  onClick={() => update({ projects: without(projects, i) })}
                />
              </div>
            ))}
          </Section>
        )}

        {education.length > 0 && (
          <Section title="Education">
            {education.map((edu, i) => (
              <div key={`${edu.institution}-${i}`} className="flex items-start gap-2 text-sm">
                <div className="flex-1">
                  <p className="font-medium">
                    {edu.institution} <SourceHint item={edu} />
                  </p>
                  <p className="text-muted-foreground">
                    {[edu.degree, edu.field_of_study, edu.date_text].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <RemoveButton
                  label={edu.institution}
                  onClick={() => update({ education: without(education, i) })}
                />
              </div>
            ))}
          </Section>
        )}

        {certifications.length > 0 && (
          <Section title="Certifications">
            {certifications.map((cert, i) => (
              <div key={`${cert.name}-${i}`} className="flex items-center gap-2 text-sm">
                <span className="flex-1">
                  {cert.name}
                  {cert.issuer ? ` · ${cert.issuer}` : ""} <SourceHint item={cert} />
                </span>
                <RemoveButton
                  label={cert.name}
                  onClick={() => update({ certifications: without(certifications, i) })}
                />
              </div>
            ))}
          </Section>
        )}

        {unsupported.length > 0 && (
          <section
            aria-labelledby="unsupported-heading"
            className="grid gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3"
          >
            <h3
              id="unsupported-heading"
              className="flex items-center gap-2 text-sm font-semibold text-amber-900"
            >
              <AlertTriangle className="size-4" />
              Not saved: could not be verified in your resume ({unsupported.length})
            </h3>
            <p className="text-xs text-amber-900">
              The parser suggested these, but the resume text does not support them, so they are
              excluded. If one is true, add it yourself so it is labeled as added by you.
            </p>
            <ul className="grid gap-1 text-sm text-amber-950">
              {unsupported.map((claim, i) => (
                <li key={i}>
                  <span className="font-medium">{claim.label}</span>{" "}
                  <span className="text-amber-800">
                    ({claim.kind}: {claim.reason.toLowerCase()})
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {dirty && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-4">
            <Button onClick={() => void onSave(draft)} disabled={saving}>
              {saving ? "Saving…" : `Save as version ${profile.version + 1}`}
            </Button>
            <Button variant="ghost" onClick={() => setDraft(profile.data)} disabled={saving}>
              Discard changes
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
