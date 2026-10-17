import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { GuestOnly } from "@/components/auth/GuestOnly";
import { SignupForm } from "@/components/auth/SignupForm";
import { SkeletonCard } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a Nora MedLink patient, doctor or admin account.",
};

export default function SignupPage() {
  return (
    <AuthLayout
      title="Create your account"
      description="It takes a minute. You can upload your first report right after."
      switchPrompt={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-brand-blue hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <GuestOnly>
        {/* The form reads ?role= from the URL, which needs a Suspense boundary. */}
        <Suspense fallback={<SkeletonCard lines={6} />}>
          <SignupForm />
        </Suspense>
      </GuestOnly>
    </AuthLayout>
  );
}
