import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { VerifyEmail } from "@/components/auth/VerifyEmail";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Confirm your email",
  description: "Confirm the email address of your Nora MedLink account.",
};

export default function VerifyEmailPage() {
  return (
    <AuthLayout title="Confirm your email" description="One moment while we check your link." switchPrompt={<span>Nora MedLink only emails confirmed addresses.</span>}>
      {/* VerifyEmail reads ?token= from the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<Skeleton className="h-12 w-full" />}>
        <VerifyEmail />
      </Suspense>
    </AuthLayout>
  );
}
