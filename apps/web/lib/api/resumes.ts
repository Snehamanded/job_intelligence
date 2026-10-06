"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { api, toApiError, type Resume } from "@/lib/api/client";
import { profileQueryKey } from "@/lib/api/profile";

export const resumesQueryKey = ["resumes"] as const;

const isBusy = (r: Resume) => r.status === "queued" || r.status === "parsing";

export function useResumes() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: resumesQueryKey,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/resumes");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    // Poll while a parse is running.
    refetchInterval: (q) => (q.state.data?.some(isBusy) ? 2000 : false),
  });

  // When a parse finishes, load the profile it produced.
  const busy = query.data?.some(isBusy) ?? false;
  const wasBusy = useRef(busy);
  useEffect(() => {
    if (wasBusy.current && !busy) {
      void queryClient.invalidateQueries({ queryKey: profileQueryKey });
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
    }
    wasBusy.current = busy;
  }, [busy, queryClient]);

  return query;
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const { data, error, response } = await api.POST("/api/resumes", {
        body: { file: "" },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", file);
          return form;
        },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: resumesQueryKey }),
  });
}

export function useReparseResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data, error, response } = await api.POST("/api/resumes/{resume_id}/reparse", {
        params: { path: { resume_id: id } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: resumesQueryKey }),
  });
}

export function useDeleteResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/resumes/{resume_id}", {
        params: { path: { resume_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resumesQueryKey });
      void queryClient.invalidateQueries({ queryKey: profileQueryKey });
    },
  });
}
