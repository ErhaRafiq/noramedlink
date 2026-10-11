"use client";

import { useEffect } from "react";
import { RotateCcw, TriangleAlert } from "lucide-react";

import { Button, ButtonLink } from "@/components/ui/button";

/** App-wide error boundary: a page crashed while rendering. */
export default function Error({ error, unstable_retry }: { error: Error & { digest?: string }; unstable_retry: () => void }) {
  useEffect(() => {
    // Surface the error in the browser console for debugging; never show stack traces to users.
    console.error(error);
  }, [error]);

  return (
    <div role="alert" className="grid min-h-screen place-items-center bg-surface-page px-4">
      <div className="max-w-md text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-rose-50 text-rose-600">
          <TriangleAlert className="h-6 w-6" aria-hidden />
        </span>
        <h1 className="mt-5 text-2xl font-semibold text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm leading-6 text-ink-muted">
          This page could not be shown. Try again, or go back to the home page.
          {error.digest ? <span className="mt-2 block font-mono text-xs">Reference: {error.digest}</span> : null}
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Button onClick={() => unstable_retry()} icon={<RotateCcw className="h-4 w-4" />}>
            Try again
          </Button>
          <ButtonLink href="/" variant="secondary">
            Go home
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
