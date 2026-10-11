import type { Metadata } from "next";
import Link from "next/link";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your Nora MedLink account.",
};

export default function LoginPage() {
  return (
    <AuthLayout
      title="Welcome back"
      description="Sign in to see your reports, vitals, medicines and appointments."
      switchPrompt={
        <>
          New to Nora MedLink?{" "}
          <Link href="/signup?role=patient" className="font-semibold text-brand-blue hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <LoginForm />
    </AuthLayout>
  );
}
