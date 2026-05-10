"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api";
import { dashboardPathForRole, saveSession } from "@/lib/auth";
import { NoraLogo } from "@/components/ui/NoraLogo";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage("");

    if (!email.trim() || !password) {
      setStatusMessage("Email and password are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      const auth = await api.login({ email: email.trim().toLowerCase(), password });
      saveSession(auth);
      router.push(dashboardPathForRole(auth.user.role));
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="app-shell grid min-h-screen place-items-center px-4 py-10">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-[#DCE8F5] bg-white shadow-[0_24px_70px_rgba(15,23,42,0.10)] lg:grid-cols-[0.95fr_1.05fr]">
        <div className="hidden bg-gradient-to-br from-[#06182F] via-[#082A46] to-[#064F59] p-10 text-white lg:block">
          <NoraLogo inverse />
          <div className="mt-16 max-w-md">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-100">
              Welcome back
            </p>
            <h1 className="mt-4 text-4xl font-black leading-tight">
              Sign in to your Nora MedLink workspace.
            </h1>
            <p className="mt-5 text-sm leading-7 text-teal-50">
              Access patient records, doctor workflows, admin controls, OCR summaries, appointments, and reminders through one secure account.
            </p>
          </div>
        </div>

        <div className="p-6 sm:p-10">
          <div className="mb-9 flex items-center justify-between gap-4">
            <NoraLogo />
            <Link href="/signup" className="secondary-button px-4 py-2">
              Signup
            </Link>
          </div>

          <div>
            <p className="section-eyebrow">Welcome back</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950">
              Login
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Continue with your verified Nora MedLink credentials.
            </p>
          </div>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="text-sm font-bold text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="form-input"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>

            <div>
              <label htmlFor="password" className="text-sm font-bold text-slate-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="form-input"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            {statusMessage ? (
              <p className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                {statusMessage}
              </p>
            ) : null}

            <button type="submit" disabled={isSubmitting} className="gradient-button w-full">
              {isSubmitting ? "Checking credentials..." : "Login securely"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
