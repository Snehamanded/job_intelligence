"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError } from "@/lib/api/client";

const settingsQueryKey = ["settings"] as const;

export function useSettings() {
  return useQuery({
    queryKey: settingsQueryKey,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/settings");
      if (!data) throw toApiError(response.status, error);
      return data;
    },
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { llm_consent: boolean }) => {
      const { data, error, response } = await api.PUT("/api/settings", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(settingsQueryKey, data),
  });
}
