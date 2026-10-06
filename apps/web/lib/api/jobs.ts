"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  api,
  toApiError,
  type ImportBatch,
  type ImportChannel,
  type ScoringSettings,
  type SearchRun,
} from "@/lib/api/client";

export type JobFilters = {
  eligibleOnly: boolean;
  source: string;
  q: string;
  limit: number;
  sort?: "rank" | "newest";
  highPriorityOnly?: boolean;
};

const isRunning = (run: SearchRun | undefined) =>
  run?.status === "queued" || run?.status === "running";

export function useJobs(filters: JobFilters) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/jobs", {
        params: {
          query: {
            eligible_only: filters.eligibleOnly,
            sort: filters.sort ?? "rank",
            high_priority_only: filters.highPriorityOnly ?? false,
            source: filters.source || undefined,
            q: filters.q || undefined,
            limit: filters.limit,
          },
        },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    placeholderData: keepPreviousData,
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/jobs/{job_id}", {
        params: { path: { job_id: id } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useDeleteJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/jobs/{job_id}", {
        params: { path: { job_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

/** Most recent search run; polls while it is running and refreshes jobs when it finishes. */
export function useLatestSearch() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["searches"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/searches");
      if (!data) throw toApiError(response.status, error);
      return data[0] ?? null;
    },
    refetchInterval: (q) => (isRunning(q.state.data ?? undefined) ? 1500 : false),
  });
  const running = isRunning(query.data ?? undefined);
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) {
      // Scoring runs right after the search: refresh status so its progress is polled.
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
    }
    wasRunning.current = running;
  }, [running, queryClient]);
  return query;
}

export function useStartSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (keywords: string[] | null) => {
      const { data, error, response } = await api.POST("/api/searches", {
        body: keywords === null ? {} : { keywords },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (run) => queryClient.setQueryData(["searches"], run),
  });
}

export function useJobSources() {
  return useQuery({
    queryKey: ["job-sources"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/job-sources");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useConnectors() {
  return useQuery({
    queryKey: ["connectors"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/connectors");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export type NewJobSource = {
  source:
    | "greenhouse"
    | "lever"
    | "ashby"
    | "remoteok"
    | "remotive"
    | "weworkremotely"
    | "jobspresso"
    | "himalayas"
    | "adzuna";
  identifier?: string;
  display_name?: string | null;
};

export function useAddJobSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewJobSource) => {
      const { data, error, response } = await api.POST("/api/job-sources", {
        body: { identifier: "", ...body },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job-sources"] }),
  });
}

export function useDeleteJobSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/job-sources/{source_id}", {
        params: { path: { source_id: id } },
      });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job-sources"] }),
  });
}

export type ImportBody =
  | { url: string }
  | { title: string; company: string; location: string; description: string; url?: string };

export function useImportJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ImportBody) => {
      const { data, error, response } = await api.POST("/api/jobs/import", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
    },
  });
}

export function useSetPriority() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, priority }: { id: string; priority: number }) => {
      const { data, error, response } = await api.PATCH("/api/jobs/{job_id}", {
        params: { path: { job_id: id } },
        body: { priority },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (job) => {
      queryClient.setQueryData(["job", job.id], job);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
    },
  });
}

/** Scoring progress; polls while jobs are still being scored. */
export function useMatchStatus() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["match-status"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/matches/status");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    refetchInterval: (q) => {
      const s = q.state.data;
      return s && s.profile_version != null && s.scored_jobs < s.total_jobs ? 2000 : false;
    },
  });
  const pending = query.data ? query.data.total_jobs - query.data.scored_jobs : 0;
  const wasPending = useRef(pending);
  useEffect(() => {
    if (wasPending.current > 0 && pending === 0) {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
    wasPending.current = pending;
  }, [pending, queryClient]);
  return query;
}

export function useRescore() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/matches/rescore");
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useScoringConfig() {
  return useQuery({
    queryKey: ["scoring-config"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/scoring-config");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useUpdateScoringConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (settings: ScoringSettings) => {
      const { data, error, response } = await api.PUT("/api/scoring-config", { body: settings });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["scoring-config"], data);
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useStartImport() {
  return useMutation({
    mutationFn: async (body: { channel: ImportChannel; text: string }) => {
      const { data, error, response } = await api.POST("/api/job-imports", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

const importRunning = (b: ImportBatch | undefined) =>
  b?.status === "queued" || b?.status === "running";

/** Polls an import until it finishes, then refreshes the job list. */
export function useImportBatch(id: string | null) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["job-imports", id],
    enabled: id != null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/job-imports/{batch_id}", {
        params: { path: { batch_id: id ?? "" } },
      });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    refetchInterval: (q) => (importRunning(q.state.data) ? 1500 : false),
  });
  const done = query.data != null && !importRunning(query.data);
  useEffect(() => {
    if (done) {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
    }
  }, [done, queryClient]);
  return query;
}
