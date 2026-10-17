"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { LogIn } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { dashboardPathForRole, safeNextPath, saveSession } from "@/lib/auth";

export function LoginForm({ next, expired = false }: { next?: string; expired?: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const auth = await api.login({ email: email.trim().toLowerCase(), password });
      saveSession(auth);
      // Back to the page the person was sent away from, if it is on this site; the page's own guard sends a
      // wrong-role visitor to their dashboard.
      router.push(safeNextPath(next) ?? dashboardPathForRole(auth.user.role));
      // Keep the button busy while the dashboard loads.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed. Please try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit} noValidate>
      <TextField
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        required
      />
      <TextField
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="Your password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />
      <p className="-mt-2 text-right text-sm">
        <Link href="/forgot-password" className="font-semibold text-brand-blue hover:underline">
          Forgot your password?
        </Link>
      </p>
      {expired && !error ? <Alert tone="info">Your session ended. Please sign in again.</Alert> : null}
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Button type="submit" size="lg" loading={isSubmitting} icon={<LogIn className="h-4 w-4" />} className="w-full">
        {isSubmitting ? "Signing in..." : "Sign in"}
      </Button>
    </form>
  );
}
