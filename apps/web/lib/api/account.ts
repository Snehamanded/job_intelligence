"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { API_URL, api, setCsrfToken, toApiError } from "@/lib/api/client";
import { meQueryKey } from "@/lib/api/auth";

/** Downloads all of the user's data as a JSON file. */
export function useExportData() {
  return useMutation({
    mutationFn: async () => {
      const response = await fetch(`${API_URL}/api/me/export`, { credentials: "include" });
      if (!response.ok) throw toApiError(response.status, await response.json().catch(() => null));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `my-data-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (password: string) => {
      const { error, response } = await api.DELETE("/api/me", { body: { password } });
      if (!response.ok) throw toApiError(response.status, error);
    },
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}
