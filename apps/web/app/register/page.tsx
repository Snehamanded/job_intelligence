import { Suspense } from "react";

import { AuthPage } from "@/components/auth/auth-page";

export default function RegisterPage() {
  return (
    <Suspense>
      <AuthPage mode="register" />
    </Suspense>
  );
}
