import { PhoneCall, Stethoscope } from "lucide-react";

import { Button, ButtonLink } from "@/components/ui/button";
import type { RequestStop } from "@/hooks/home-visits/use-home-visit-request";

/**
 * What replaces the form when the server stops the request. An emergency shows the 1122 notice and offers
 * nothing to book (AGENTS.md 6.3); a clinic-only problem points to a clinic appointment. Nothing was saved.
 */
export function StopNotice({ stop, onStartOver }: { stop: RequestStop; onStartOver: () => void }) {
  if (stop.kind === "emergency") {
    return (
      <div role="alert" className="rounded-card border border-rose-200 bg-rose-50 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <PhoneCall className="mt-0.5 h-6 w-6 flex-shrink-0 text-rose-600" aria-hidden />
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-rose-900">This may be an emergency</h2>
            <p className="mt-1 text-sm font-semibold leading-6 text-rose-900">{stop.message}</p>
            {stop.flags.length ? (
              <p className="mt-2 text-sm leading-6 text-rose-900">What we noticed: {stop.flags.join(", ")}.</p>
            ) : null}
            <p className="mt-2 text-sm leading-6 text-rose-900">
              Nothing was saved and no doctor was contacted. A home visit is not the right help for an emergency.
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" className="mt-4" onClick={onStartOver}>
          Start over
        </Button>
      </div>
    );
  }
  return (
    <div role="status" className="rounded-card border border-amber-200 bg-amber-50 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <Stethoscope className="mt-0.5 h-6 w-6 flex-shrink-0 text-amber-600" aria-hidden />
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-amber-900">Better seen in a clinic</h2>
          <p className="mt-1 text-sm leading-6 text-amber-900">{stop.message}</p>
          <p className="mt-1 text-sm leading-6 text-amber-900">Nothing was saved. If it gets worse or feels urgent, call 1122.</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <ButtonLink href="/doctors" size="sm">
          Find a doctor and book
        </ButtonLink>
        <Button variant="secondary" size="sm" onClick={onStartOver}>
          Start over
        </Button>
      </div>
    </div>
  );
}
