"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_URL, api, toApiError } from "@/lib/api/client";

const one = (id: string) => ["cover-letter", id] as const;

export function useCoverLetters(jobId?: string) {
  return useQuery({
    queryKey: ["cover-letters", jobId ?? "all"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/cover-letters", {
        params: { query: jobId ? { job_id: jobId } : {} },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useCoverLetter(id: string) {
  return useQuery({
    queryKey: one(id),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/cover-letters/{letter_id}", {
        params: { path: { letter_id: id } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 1500 : false),
  });
}

export type NewCoverLetter = {
  job_id: string;
  resume_version_id?: string | null;
  tone: "professional" | "warm" | "concise";
  length: "short" | "medium";
};

export function useCreateCoverLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewCoverLetter) => {
      const { data, error, response } = await api.POST("/api/cover-letters", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(one(data.id), data);
      void queryClient.invalidateQueries({ queryKey: ["cover-letters"] });
    },
  });
}

export type SentenceEdits = {
  updates?: Record<string, { included?: boolean; text?: string }>;
  add?: { paragraph_id: string; text: string }[];
};

export function useEditSentences(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: SentenceEdits) => {
      const { data, error, response } = await api.PATCH(
        "/api/cover-letters/{letter_id}/sentences",
        {
          params: { path: { letter_id: id } },
          body: { updates: body.updates ?? {}, add: body.add ?? [] },
        },
      );
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(one(id), data),
  });
}

export function useSaveCoverLetter(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string | null) => {
      const { data, error, response } = await api.POST("/api/cover-letters/{letter_id}/save", {
        params: { path: { letter_id: id } },
        body: { name },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(one(id), data);
      void queryClient.invalidateQueries({ queryKey: ["cover-letters"] });
    },
  });
}

export function useDeleteCoverLetter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/cover-letters/{letter_id}", {
        params: { path: { letter_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cover-letters"] }),
  });
}

export const coverLetterDocxUrl = (id: string) => `${API_URL}/api/cover-letters/${id}/docx`;
