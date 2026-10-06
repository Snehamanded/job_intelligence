"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDeleteAccount, useExportData } from "@/lib/api/account";

export function DataControls() {
  const router = useRouter();
  const exportData = useExportData();
  const deleteAccount = useDeleteAccount();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");

  const onDelete = (event: FormEvent) => {
    event.preventDefault();
    deleteAccount.mutate(password, { onSuccess: () => router.replace("/login") });
  };

  return (
    <div className="grid gap-6 text-sm">
      <div className="grid gap-2">
        <p className="text-muted-foreground">
          Download everything stored about you: account, settings, resumes (with extracted text),
          every profile version and AI usage.
        </p>
        <div>
          <Button
            variant="outline"
            onClick={() => exportData.mutate()}
            disabled={exportData.isPending}
          >
            {exportData.isPending ? "Preparing…" : "Export my data"}
          </Button>
        </div>
        {exportData.error && <p className="text-destructive">{exportData.error.message}</p>}
      </div>

      <div className="grid gap-2 border-t pt-6">
        <p className="font-medium text-destructive">Delete account</p>
        <p className="text-muted-foreground">
          Permanently deletes your account, resumes, profiles and settings. This cannot be undone.
        </p>
        {!confirming ? (
          <div>
            <Button variant="destructive" onClick={() => setConfirming(true)}>
              Delete my account
            </Button>
          </div>
        ) : (
          <form onSubmit={onDelete} className="grid max-w-sm gap-2">
            <Label htmlFor="delete-password">Enter your password to confirm</Label>
            <Input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {deleteAccount.error && (
              <p role="alert" className="text-destructive">
                {deleteAccount.error.message}
              </p>
            )}
            <div className="flex gap-2">
              <Button
                type="submit"
                variant="destructive"
                disabled={!password || deleteAccount.isPending}
              >
                {deleteAccount.isPending ? "Deleting…" : "Permanently delete"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
