"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  toApiError,
  type ApplicationDetail,
  type Interview,
  type Stage,
} from "@/lib/api/client";

const keys = {
  list: ["applications"] as const,
  one: (id: string) => ["application", id] as const,
};

function useInvalidate() {
  const queryClient = useQueryClient();
  return (id?: string) => {
    void queryClient.invalidateQueries({ queryKey: keys.list });
    void queryClient.invalidateQueries({ queryKey: ["analytics"] });
    void queryClient.invalidateQueries({ queryKey: ["upcoming-interviews"] });
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["job"] });
    if (id) void queryClient.invalidateQueries({ queryKey: keys.one(id) });
  };
}

export function useApplications() {
  return useQuery({
    queryKey: keys.list,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/applications");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useApplication(id: string) {
  return useQuery({
    queryKey: keys.one(id),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/applications/{application_id}", {
        params: { path: { application_id: id } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export type NewApplication =
  | { job_id: string; stage: Stage }
  | { title: string; company: string; location?: string; url?: string; stage: Stage };

export function useCreateApplication() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: NewApplication) => {
      const { data, error, response } = await api.POST("/api/applications", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => invalidate(),
  });
}

export type ApplicationPatch = {
  stage?: Stage;
  position?: number;
  applied_at?: string | null;
  next_action?: string | null;
  next_action_date?: string | null;
};

export function useUpdateApplication() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, ...body }: ApplicationPatch & { id: string }) => {
      const { data, error, response } = await api.PATCH("/api/applications/{application_id}", {
        params: { path: { application_id: id } },
        body,
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(keys.one(data.id), data);
      invalidate();
    },
  });
}

export function useDeleteApplication() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/applications/{application_id}", {
        params: { path: { application_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => invalidate(),
  });
}

export function useAddNote(applicationId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: string) => {
      const { data, error, response } = await api.POST("/api/applications/{application_id}/notes", {
        params: { path: { application_id: applicationId } },
        body: { body },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => invalidate(applicationId),
  });
}

export function useDeleteNote(applicationId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (noteId: string) => {
      const { error, response } = await api.DELETE("/api/notes/{note_id}", {
        params: { path: { note_id: noteId } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => invalidate(applicationId),
  });
}

export type NewInterview = {
  scheduled_at: string;
  kind: Interview["kind"];
  location?: string;
  checklist: { text: string; done: boolean }[];
};

export function useAddInterview(applicationId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (body: NewInterview) => {
      const { data, error, response } = await api.POST(
        "/api/applications/{application_id}/interviews",
        { params: { path: { application_id: applicationId } }, body },
      );
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => invalidate(applicationId),
  });
}

type InterviewPatch = {
  id: string;
  outcome?: Interview["outcome"];
  checklist?: Interview["checklist"];
};

export function useUpdateInterview(applicationId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidate();
  const key = keys.one(applicationId);
  return useMutation({
    mutationFn: async ({ id, ...body }: InterviewPatch) => {
      const { data, error, response } = await api.PATCH("/api/interviews/{interview_id}", {
        params: { path: { interview_id: id } },
        body,
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    // Checklist ticks and outcomes show immediately; rolled back if the server refuses.
    onMutate: async ({ id, ...changes }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<ApplicationDetail>(key);
      if (previous) {
        queryClient.setQueryData<ApplicationDetail>(key, {
          ...previous,
          interviews: previous.interviews.map((iv) => (iv.id === id ? { ...iv, ...changes } : iv)),
        });
      }
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSettled: () => invalidate(applicationId),
  });
}

export function useDeleteInterview(applicationId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/interviews/{interview_id}", {
        params: { path: { interview_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => invalidate(applicationId),
  });
}

export function useUpcomingInterviews() {
  return useQuery({
    queryKey: ["upcoming-interviews"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/interviews/upcoming");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/analytics");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}
