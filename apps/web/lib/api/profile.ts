"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError, type Preferences, type ProfileData } from "@/lib/api/client";

export const profileQueryKey = ["profile"] as const;

export function useProfile() {
  return useQuery({
    queryKey: profileQueryKey,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/profile");
      if (!response.ok) throw toApiError(response.status, error);
      return data ?? null;
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { data: ProfileData; preferences: Preferences }) => {
      const { data, error, response } = await api.PUT("/api/profile", { body });
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(profileQueryKey, data);
      // A new profile version means jobs get rescored.
      void queryClient.invalidateQueries({ queryKey: ["match-status"] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
