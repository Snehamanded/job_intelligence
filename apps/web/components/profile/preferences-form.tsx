"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Preferences } from "@/lib/api/client";

const EMPLOYMENT = [
  { value: "full_time", label: "Full-time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
  { value: "part_time", label: "Part-time" },
] as const;

const REMOTE = [
  { value: "none", label: "Not looking for remote" },
  { value: "india", label: "Remote within India" },
  { value: "worldwide", label: "Remote worldwide" },
] as const;

const splitList = (value: string) =>
  value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

export const preferencesSchema = z
  .object({
    targetRoles: z.string().refine((v) => splitList(v).length <= 10, "Up to 10 roles."),
    remoteScope: z.enum(["none", "india", "worldwide"]),
    onsiteLocations: z.string().refine((v) => splitList(v).length <= 20, "Up to 20 cities."),
    openTo: z
      .array(z.enum(["full_time", "contract", "internship", "part_time"]))
      .min(1, "Choose at least one employment type."),
    minSalary: z
      .string()
      .trim()
      .refine((v) => v === "" || /^\d+$/.test(v), "Enter a whole number, or leave empty."),
    currency: z
      .string()
      .trim()
      .refine((v) => v === "" || /^[A-Za-z]{3}$/.test(v), "Use a 3-letter code such as INR."),
    salaryUnknownPolicy: z.enum(["include", "exclude"]),
  })
  .refine((v) => v.minSalary === "" || v.currency !== "", {
    message: "Choose a currency for the minimum salary.",
    path: ["currency"],
  });

type FormValues = z.infer<typeof preferencesSchema>;

function toForm(p: Preferences): FormValues {
  return {
    targetRoles: (p.target_roles ?? []).join(", "),
    remoteScope: p.remote_scope ?? "none",
    onsiteLocations: (p.onsite_locations ?? []).join(", "),
    openTo: p.open_to ?? ["full_time"],
    minSalary: p.min_salary == null ? "" : String(p.min_salary),
    currency: p.currency ?? "",
    salaryUnknownPolicy: p.salary_unknown_policy ?? "include",
  };
}

function fromForm(v: FormValues): Preferences {
  return {
    target_roles: splitList(v.targetRoles),
    remote_scope: v.remoteScope,
    onsite_locations: splitList(v.onsiteLocations),
    open_to: v.openTo,
    min_salary: v.minSalary === "" ? null : Number(v.minSalary),
    currency: v.currency === "" ? null : v.currency.toUpperCase(),
    salary_unknown_policy: v.salaryUnknownPolicy,
  };
}

type Props = {
  initial: Preferences;
  onSubmit: (preferences: Preferences) => Promise<unknown>;
  error?: string | null;
  saved?: boolean;
};

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-sm text-destructive">{message}</p> : null;
}

export function PreferencesForm({ initial, onSubmit, error, saved }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: toForm(initial),
  });

  const submit = handleSubmit(async (values) => {
    try {
      await onSubmit(fromForm(values));
      reset(values);
    } catch {
      // Shown through `error`.
    }
  });

  return (
    <form onSubmit={submit} noValidate className="grid max-w-2xl gap-6">
      <div className="grid gap-2">
        <Label htmlFor="targetRoles">Target roles</Label>
        <Input
          id="targetRoles"
          placeholder="Backend Engineer, Python Developer"
          {...register("targetRoles")}
        />
        <p className="text-xs text-muted-foreground">Comma-separated.</p>
        <FieldError message={errors.targetRoles?.message} />
      </div>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Remote work</legend>
        {REMOTE.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input type="radio" value={option.value} {...register("remoteScope")} />
            {option.label}
          </label>
        ))}
      </fieldset>

      <div className="grid gap-2">
        <Label htmlFor="onsiteLocations">Cities for on-site or hybrid work</Label>
        <Input
          id="onsiteLocations"
          placeholder="Bengaluru, Hyderabad"
          {...register("onsiteLocations")}
        />
        <p className="text-xs text-muted-foreground">
          Comma-separated. Names are standardized (for example, Bangalore becomes Bengaluru).
        </p>
        <FieldError message={errors.onsiteLocations?.message} />
      </div>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Open to</legend>
        {EMPLOYMENT.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input type="checkbox" value={option.value} {...register("openTo")} />
            {option.label}
          </label>
        ))}
        <FieldError message={errors.openTo?.message} />
      </fieldset>

      <div className="grid gap-2 sm:grid-cols-[1fr_8rem]">
        <div className="grid gap-2">
          <Label htmlFor="minSalary">Minimum annual salary</Label>
          <Input
            id="minSalary"
            inputMode="numeric"
            placeholder="1200000"
            {...register("minSalary")}
          />
          <FieldError message={errors.minSalary?.message} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="currency">Currency</Label>
          <Input id="currency" placeholder="INR" maxLength={3} {...register("currency")} />
          <FieldError message={errors.currency?.message} />
        </div>
      </div>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Jobs that don&apos;t list a salary</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" value="include" {...register("salaryUnknownPolicy")} />
          Include them
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" value="exclude" {...register("salaryUnknownPolicy")} />
          Hide them
        </label>
      </fieldset>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={isSubmitting || !isDirty}>
          {isSubmitting ? "Saving…" : "Save preferences"}
        </Button>
        {saved && !isDirty && <span className="text-sm text-muted-foreground">Saved.</span>}
      </div>
    </form>
  );
}
