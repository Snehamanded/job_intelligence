"use client";

import { Loader2 } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ScoringForm } from "@/components/jobs/scoring-form";
import { PreferencesForm } from "@/components/profile/preferences-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useScoringConfig, useUpdateScoringConfig } from "@/lib/api/jobs";
import type { Preferences } from "@/lib/api/client";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";

const DEFAULTS: Preferences = {
  target_roles: [],
  remote_scope: "none",
  onsite_locations: [],
  open_to: ["full_time"],
  min_salary: null,
  currency: null,
  salary_unknown_policy: "include",
};

export default function PreferencesPage() {
  const profile = useProfile();
  const update = useUpdateProfile();
  const scoring = useScoringConfig();
  const updateScoring = useUpdateScoringConfig();

  return (
    <>
      <PageHeader
        title="Preferences"
        description="What you are looking for. Used to filter and rank jobs. Each save is a new profile version."
      />
      <Card>
        <CardContent>
          {profile.isPending ? (
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          ) : (
            <PreferencesForm
              key={profile.data?.id ?? "new"}
              initial={profile.data?.preferences ?? DEFAULTS}
              error={update.error?.message}
              saved={update.isSuccess}
              onSubmit={(preferences) =>
                update.mutateAsync({ data: profile.data?.data ?? {}, preferences })
              }
            />
          )}
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>How jobs are ranked</CardTitle>
          <CardDescription>
            Adjust what matters most. Saving creates a new scoring version and rescores your jobs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {scoring.data && (
            <ScoringForm
              key={scoring.data.version}
              initial={scoring.data.settings}
              error={updateScoring.error?.message}
              onSubmit={(settings) => updateScoring.mutateAsync(settings)}
            />
          )}
        </CardContent>
      </Card>
    </>
  );
}
