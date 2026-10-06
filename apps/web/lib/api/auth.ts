"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, setCsrfToken, toApiError, type AuthResponse, type User } from "@/lib/api/client";

export const meQueryKey = ["me"] as const;

type Credentials = { email: string; password: string };

/** The signed-in user, or null when there is no valid session. */
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<User | null> => {
      const { data, error, response } = await api.GET("/api/me");
      if (response.status === 401) return null;
      if (!data) throw toApiError(response.status, error);
      return data;
    },
    retry: false,
    staleTime: 60_000,
  });
}

function useStartSession(start: (body: Credentials) => Promise<AuthResponse>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: start,
    onSuccess: (data) => {
      setCsrfToken(data.csrf_token);
      queryClient.setQueryData(meQueryKey, data.user);
    },
  });
}

export function useLogin() {
  return useStartSession(async (body) => {
    const { data, error, response } = await api.POST("/api/auth/login", { body });
    if (!data) throw toApiError(response.status, error);
    return data;
  });
}

export function useRegister() {
  return useStartSession(async (body) => {
    const { data, error, response } = await api.POST("/api/auth/register", { body });
    if (!data) throw toApiError(response.status, error);
    return data;
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/auth/logout");
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSettled: () => {
      setCsrfToken(null);
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}
