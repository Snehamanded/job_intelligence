"use client";

import { Briefcase } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { AuthForm } from "@/components/auth/auth-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLogin, useMe, useRegister } from "@/lib/api/auth";
import { safeNextPath } from "@/lib/safe-redirect";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const { data: user } = useMe();
  const login = useLogin();
  const registerUser = useRegister();
  const mutation = mode === "login" ? login : registerUser;

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, next, router]);

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 text-primary">
            <Briefcase className="size-5" />
            <span className="font-semibold">Job Intelligence</span>
          </div>
          <CardTitle className="text-xl">
            {mode === "login" ? "Sign in" : "Create your account"}
          </CardTitle>
          <CardDescription>
            {mode === "login"
              ? "Welcome back. Sign in to see your ranked jobs."
              : "Your personal job search assistant."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <AuthForm
            mode={mode}
            onSubmit={(values) => mutation.mutateAsync(values)}
            error={mutation.error?.message}
          />
          <p className="text-center text-sm text-muted-foreground">
            {mode === "login" ? (
              <>
                No account?{" "}
                <Link href="/register" className="text-primary underline-offset-4 hover:underline">
                  Create one
                </Link>
              </>
            ) : (
              <>
                Already registered?{" "}
                <Link href="/login" className="text-primary underline-offset-4 hover:underline">
                  Sign in
                </Link>
              </>
            )}
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
