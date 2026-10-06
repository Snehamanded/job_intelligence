import { Suspense } from "react";

import { AuthPage } from "@/components/auth/auth-page";

export default function LoginPage() {
  return (
    <Suspense>
      <AuthPage mode="login" />
    </Suspense>
  );
}
