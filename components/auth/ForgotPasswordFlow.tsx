"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, KeyRound, Mail } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api";

const RESEND_SECONDS = 60; // the server allows a new code once a minute

type Step = "email" | "code" | "done";

/**
 * Forgot password in two steps: ask for a code by email, then enter the 6-digit code with a new password.
 * The first step gives the same answer whether or not the address has an account, so this page cannot be
 * used to find out who is registered. A password change signs the account out everywhere.
 */
export function ForgotPasswordFlow() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; code?: string; password?: string; confirm?: string }>({});
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((seconds) => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  function failure(err: unknown, fallback: string) {
    if (err instanceof ApiError && err.status === 429 && err.retryAfterSeconds) setWait(Math.max(err.retryAfterSeconds, 1));
    setError(err instanceof Error ? err.message : fallback);
  }

  async function requestCode(event?: FormEvent) {
    event?.preventDefault();
    if (busy) return;
    setError("");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setFieldErrors({ email: "Enter the email address of your account." });
      return;
    }
    setFieldErrors({});
    setBusy(true);
    try {
      const answer = await api.forgotPassword(email.trim().toLowerCase());
      setInfo(answer.message);
      setStep("code");
      setWait(RESEND_SECONDS);
    } catch (err) {
      failure(err, "The code could not be requested. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError("");
    const found: typeof fieldErrors = {};
    if (!/^\d{6}$/.test(code.trim())) found.code = "Enter the 6 digits from the email.";
    if (password.length < 8) found.password = "Use at least 8 characters.";
    if (confirm !== password) found.confirm = "Passwords do not match.";
    setFieldErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await api.resetPassword({ email: email.trim().toLowerCase(), code: code.trim(), new_password: password, confirm_password: confirm });
      setStep("done");
    } catch (err) {
      failure(err, "The password could not be changed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (step === "done") {
    return (
      <div className="space-y-5">
        <Alert tone="success" title="Your password was changed">
          You were signed out everywhere. Sign in with your new password.
        </Alert>
        <ButtonLink href="/login" size="lg" className="w-full" icon={<CheckCircle2 className="h-4 w-4" />}>
          Go to sign in
        </ButtonLink>
      </div>
    );
  }

  if (step === "email") {
    return (
      <form className="space-y-5" onSubmit={requestCode} noValidate>
        <p className="text-sm leading-6 text-ink-muted">Enter the email address of your account and we will send you a 6-digit code.</p>
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors.email}
          required
        />
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Button type="submit" size="lg" loading={busy} disabled={wait > 0} icon={<Mail className="h-4 w-4" />} className="w-full">
          {busy ? "Sending..." : wait > 0 ? `Wait ${wait} s to ask again` : "Send me a code"}
        </Button>
        <p className="text-center text-sm text-ink-muted">
          <Link href="/login" className="font-semibold text-brand-blue hover:underline">
            Back to sign in
          </Link>
        </p>
      </form>
    );
  }

  return (
    <form className="space-y-5" onSubmit={changePassword} noValidate>
      <Alert tone="info" title="Check your email">
        {info} It was sent to <span className="break-all font-semibold">{email.trim().toLowerCase()}</span>. Look in your spam folder if it does not arrive in a minute.
      </Alert>
      <TextField
        label="6-digit code"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        placeholder="123456"
        value={code}
        onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
        error={fieldErrors.code}
        required
      />
      <TextField
        label="New password"
        type="password"
        autoComplete="new-password"
        hint="At least 8 characters."
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        error={fieldErrors.password}
        required
      />
      <TextField
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        value={confirm}
        onChange={(event) => setConfirm(event.target.value)}
        error={fieldErrors.confirm}
        required
      />
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Button type="submit" size="lg" loading={busy} icon={<KeyRound className="h-4 w-4" />} className="w-full">
        {busy ? "Changing..." : "Change my password"}
      </Button>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <Button type="button" variant="ghost" size="sm" disabled={busy || wait > 0} onClick={() => void requestCode()}>
          {wait > 0 ? `Send a new code in ${wait} s` : "Send a new code"}
        </Button>
        <button
          type="button"
          onClick={() => {
            setStep("email");
            setError("");
            setCode("");
          }}
          className="font-semibold text-brand-blue hover:underline"
        >
          Use a different email
        </button>
      </div>
    </form>
  );
}
