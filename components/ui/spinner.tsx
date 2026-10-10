import { Loader2 } from "lucide-react";

import { cn } from "@/lib/cn";

/** Inline spinner. Pass `label` when the spinner is the only sign that something is loading. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role={label ? "status" : undefined} className="inline-flex items-center">
      <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-hidden />
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  );
}

/** Full-screen loader for a page that cannot show anything until it has checked the session. */
export function PageLoader({ message = "Loading..." }: { message?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid min-h-screen place-items-center bg-surface-page px-4">
      <div className="flex flex-col items-center gap-4">
        <span className="relative grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-blue to-brand-teal shadow-card">
          <span className="absolute h-8 w-3 rounded-full bg-white" />
          <span className="absolute h-3 w-8 rounded-full bg-white" />
        </span>
        <span className="flex items-center gap-2 text-sm font-medium text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin text-brand-blue" aria-hidden />
          {message}
        </span>
      </div>
    </div>
  );
}

/** Small error panel with an optional retry action. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="grid min-h-screen place-items-center bg-surface-page px-4">
      <div className="max-w-md rounded-card border border-rose-100 bg-white p-6 text-center shadow-card">
        <p className="text-sm font-semibold text-rose-700">{message}</p>
        {onRetry ? (
          <button type="button" onClick={onRetry} className="secondary-button mt-4">
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
