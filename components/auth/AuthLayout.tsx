import Link from "next/link";
import type { ReactNode } from "react";
import { BadgeCheck, KeyRound, ShieldCheck } from "lucide-react";

import { NoraLogo } from "@/components/ui/NoraLogo";

const POINTS = [
  { icon: KeyRound, text: "Doctors open your file only with a one-time code you give them." },
  { icon: BadgeCheck, text: "Doctor accounts are verified by an administrator before patients can book them." },
  { icon: ShieldCheck, text: "Summaries are advisory and never replace a clinician." },
];

/** Two-column frame for sign in and sign up: brand panel on large screens, form card always. */
export function AuthLayout({
  title,
  description,
  switchPrompt,
  children,
}: {
  title: string;
  description: string;
  /** e.g. "New here? Create an account" link under the heading. */
  switchPrompt: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-screen bg-surface-page lg:grid-cols-[0.9fr_1.1fr]">
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-navy via-brand-navy-soft to-[#064F59] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <NoraLogo inverse />
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">Your health record, explained and in your hands.</h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-sm leading-6 text-slate-200">
                <Icon className="mt-0.5 h-5 w-5 flex-shrink-0 text-teal-300" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-slate-400">Academic prototype · advisory only · in an emergency call 1122</p>
      </aside>

      <main className="flex flex-col px-4 py-8 sm:px-8 lg:px-16">
        <div className="flex items-center justify-between lg:justify-end">
          <span className="lg:hidden">
            <NoraLogo />
          </span>
          <Link href="/" className="text-sm font-medium text-ink-muted transition-colors hover:text-ink">
            Back to home
          </Link>
        </div>
        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center py-10">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-ink-muted">{description}</p>
          <p className="mt-1 text-sm text-ink-muted">{switchPrompt}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
