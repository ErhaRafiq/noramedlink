import type { Metadata } from "next";
import Link from "next/link";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { ForgotPasswordFlow } from "@/components/auth/ForgotPasswordFlow";

export const metadata: Metadata = {
  title: "Reset your password",
  description: "Get a 6-digit code by email and choose a new Nora MedLink password.",
};

export default function ForgotPasswordPage() {
  return (
    <AuthLayout
      title="Reset your password"
      description="We will email you a code. It works for 10 minutes."
      switchPrompt={
        <>
          Remembered it?{" "}
          <Link href="/login" className="font-semibold text-brand-blue hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <ForgotPasswordFlow />
    </AuthLayout>
  );
}
