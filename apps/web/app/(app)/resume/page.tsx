"use client";

import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { ProfileReview } from "@/components/profile/profile-review";
import { ResumeList } from "@/components/resume/resume-list";
import { UploadCard } from "@/components/resume/upload-card";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";
import { useDeleteResume, useReparseResume, useResumes, useUploadResume } from "@/lib/api/resumes";
import { useSettings } from "@/lib/api/settings";

export default function ResumePage() {
  const resumes = useResumes();
  const profile = useProfile();
  const settings = useSettings();
  const uploadResume = useUploadResume();
  const reparse = useReparseResume();
  const remove = useDeleteResume();
  const update = useUpdateProfile();

  const busyId = reparse.isPending ? reparse.variables : remove.isPending ? remove.variables : null;

  return (
    <>
      <PageHeader
        title="Resume"
        description="Upload your resume, then check what was extracted from it."
      />
      <div className="grid gap-6">
        {settings.data && !settings.data.llm_consent && (
          <p className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground">
            AI processing is off, so resumes are read with basic parsing on this server only.{" "}
            <Link href="/settings" className="text-primary underline-offset-4 hover:underline">
              Turn on AI processing
            </Link>{" "}
            for better results.
          </p>
        )}
        <UploadCard
          onUpload={(file) => uploadResume.mutateAsync(file)}
          uploading={uploadResume.isPending}
          serverError={uploadResume.error?.message}
        />
        <ResumeList
          resumes={resumes.data ?? []}
          currentResumeId={profile.data?.resume_id}
          onReparse={(id) => reparse.mutate(id)}
          onDelete={(id) => remove.mutate(id)}
          busyId={busyId}
        />
        {(reparse.error ?? remove.error) && (
          <p role="alert" className="text-sm text-destructive">
            {(reparse.error ?? remove.error)?.message}
          </p>
        )}
        {profile.data && (
          <ProfileReview
            profile={profile.data}
            saving={update.isPending}
            error={update.error?.message}
            onSave={(data) => update.mutateAsync({ data, preferences: profile.data!.preferences })}
          />
        )}
      </div>
    </>
  );
}
