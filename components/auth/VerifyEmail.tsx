"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

type State = { status: "checking" } | { status: "done"; message: string } | { status: "failed"; message: string };

/**
 * Opened from the link in the confirmation email. The page makes the call (a POST), so a mail scanner that only
 * fetches the link cannot use the link up. It runs once per visit.
 */
export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const started = useRef(false);
  const [state, setState] = useState<State>(token ? { status: "checking" } : { status: "failed", message: "This link has no confirmation code. Open the link from the email again." });

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    api
      .verifyEmail(token)
      .then((answer) => setState({ status: "done", message: answer.message }))
      .catch((err: unknown) => setState({ status: "failed", message: err instanceof Error ? err.message : "The link could not be checked. Please try again." }));
  }, [token]);

  if (state.status === "checking") {
    return (
      <div role="status" aria-label="Confirming your email" className="space-y-3">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }
  if (state.status === "done") {
    return (
      <div className="space-y-5">
        <Alert tone="success" title="Email confirmed">
          {state.message} You will now get appointment confirmations and reminders by email.
        </Alert>
        <ButtonLink href="/login" size="lg" className="w-full">
          Continue to sign in
        </ButtonLink>
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <Alert tone="error" title="This link did not work">
        {state.message}
      </Alert>
      <ButtonLink href="/login" variant="secondary" size="lg" className="w-full">
        Sign in to get a new link
      </ButtonLink>
    </div>
  );
}
