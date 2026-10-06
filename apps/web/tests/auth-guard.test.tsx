import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/settings",
}));

const get = vi.fn();
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: { GET: (...args: unknown[]) => get(...args) } };
});

import { AuthGuard } from "@/components/auth-guard";

function renderGuarded(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthGuard>{children}</AuthGuard>
    </QueryClientProvider>,
  );
}

describe("AuthGuard", () => {
  beforeEach(() => {
    replace.mockReset();
    get.mockReset();
  });

  it("redirects to /login with the current path when not signed in", async () => {
    get.mockResolvedValue({
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderGuarded(<p>secret content</p>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2Fsettings"));
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("renders the protected content when signed in", async () => {
    get.mockResolvedValue({
      data: { id: "u1", email: "sneha@example.com", created_at: "2026-10-05T00:00:00Z" },
      error: undefined,
      response: { status: 200 },
    });
    renderGuarded(<p>secret content</p>);

    expect(await screen.findByText("secret content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows an error instead of redirecting when the API is unreachable", async () => {
    get.mockResolvedValue({ data: undefined, error: undefined, response: { status: 500 } });
    renderGuarded(<p>secret content</p>);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the API");
    expect(replace).not.toHaveBeenCalled();
  });
});
