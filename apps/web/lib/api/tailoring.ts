"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_URL, api, toApiError } from "@/lib/api/client";

const one = (id: string) => ["tailoring", id] as const;

export function useTailoringList(jobId?: string) {
  return useQuery({
    queryKey: ["tailoring-list", jobId ?? "all"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/tailoring", {
        params: { query: jobId ? { job_id: jobId } : {} },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useTailoring(id: string) {
  return useQuery({
    queryKey: one(id),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/tailoring/{version_id}", {
        params: { path: { version_id: id } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 1500 : false),
  });
}

export function useStartTailoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data, error, response } = await api.POST("/api/tailoring", {
        body: { job_id: jobId },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(one(data.id), data);
      void queryClient.invalidateQueries({ queryKey: ["tailoring-list"] });
    },
  });
}

export function useDecide(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (decisions: Record<string, "accepted" | "rejected" | "pending">) => {
      const { data, error, response } = await api.PATCH("/api/tailoring/{version_id}/decisions", {
        params: { path: { version_id: id } },
        body: { decisions },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(one(id), data),
  });
}

export function useSaveVersion(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string | null) => {
      const { data, error, response } = await api.POST("/api/tailoring/{version_id}/save", {
        params: { path: { version_id: id } },
        body: { name },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(one(id), data);
      void queryClient.invalidateQueries({ queryKey: ["tailoring-list"] });
    },
  });
}

export function useDeleteVersion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/tailoring/{version_id}", {
        params: { path: { version_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tailoring-list"] }),
  });
}

export const docxUrl = (id: string) => `${API_URL}/api/tailoring/${id}/docx`;
export const pdfUrl = (id: string) => `${API_URL}/api/tailoring/${id}/pdf`;
