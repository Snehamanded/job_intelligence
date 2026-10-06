"use client";

import { DataControls } from "@/components/account/data-controls";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useMe } from "@/lib/api/auth";
import { useSettings, useUpdateSettings } from "@/lib/api/settings";

export default function SettingsPage() {
  const { data: user } = useMe();
  const settings = useSettings();
  const update = useUpdateSettings();

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid max-w-2xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <p className="text-muted-foreground">Signed in as</p>
            <p className="font-medium">{user?.email}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI processing</CardTitle>
            <CardDescription>
              Resume parsing, matching and tailoring send your resume text to a third-party LLM
              provider (OpenAI or Google Gemini). Nothing is sent until you turn this on, and you
              can turn it off at any time.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="llm-consent">Allow sending my resume to an LLM provider</Label>
              <Switch
                id="llm-consent"
                checked={settings.data?.llm_consent ?? false}
                disabled={settings.isPending || update.isPending}
                onCheckedChange={(checked) => update.mutate({ llm_consent: checked })}
              />
            </div>
            {settings.data?.llm_consent_at && (
              <p className="text-xs text-muted-foreground">
                Consent given {new Date(settings.data.llm_consent_at).toLocaleString()}
              </p>
            )}
            {(settings.error ?? update.error) && (
              <p role="alert" className="text-sm text-destructive">
                {(settings.error ?? update.error)?.message}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Your data</CardTitle>
            <CardDescription>Export or permanently delete all of your data.</CardDescription>
          </CardHeader>
          <CardContent>
            <DataControls />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
