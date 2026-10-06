"use client";

import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useMe } from "@/lib/api/auth";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isPending, isError } = useMe();

  useEffect(() => {
    if (!isPending && user === null) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isPending, user, pathname, router]);

  if (isError) {
    return (
      <div role="alert" className="flex min-h-screen items-center justify-center p-6 text-sm">
        Cannot reach the API. Check that it is running and try again.
      </div>
    );
  }
  if (isPending || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center" aria-label="Loading">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return <>{children}</>;
}
