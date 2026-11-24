"use client";

import { useState } from "react";
import { Check, Circle, PhoneCall } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useNow } from "@/hooks/use-now";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";
import type { PatientHomeVisit } from "@/lib/types";

const STEPS: Array<{ key: keyof PatientHomeVisit; label: string }> = [
  { key: "created_at", label: "Request sent" },
  { key: "accepted_at", label: "Doctor accepted" },
  { key: "en_route_at", label: "Doctor on the way" },
  { key: "arrived_at", label: "Doctor arrived" },
  { key: "completed_at", label: "Visit finished" },
  { key: "closed_at", label: "Summary saved to your record" },
];

const CANCELLABLE = new Set(["offered", "accepted", "en_route"]);

function countdown(expiresAt: string | null, now: number) {
  if (!expiresAt) return null;
  const left = Math.max(0, Math.round((new Date(expiresAt).getTime() - now) / 1000));
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
}

/** The live visit: where it is now, with the time of every step. Only the status moves: there is no map or live pin. */
export function VisitTracker({
  visit,
  onCancel,
  busy,
  error,
}: {
  visit: PatientHomeVisit;
  onCancel: () => void;
  busy: boolean;
  error: string;
}) {
  const [confirming, setConfirming] = useState(false);
  const now = useNow(visit.status === "offered");
  const left = visit.status === "offered" ? countdown(visit.offer_expires_at, now) : null;
  const currentIndex = STEPS.reduce((last, step, index) => (visit[step.key] ? index : last), 0);

  return (
    <section aria-labelledby="tracker-title" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 id="tracker-title" className="text-base font-semibold text-ink">
          Your home visit
        </h2>
        <p className="text-sm font-medium text-brand-blue" role="status">
          {visit.status_label}
        </p>
      </div>

      {visit.status === "offered" ? (
        <Alert tone="info" className="mt-4">
          {visit.mode === "choose" && visit.doctor
            ? `Waiting for ${visit.doctor.name} to answer. They have 10 minutes.`
            : `Asking doctor ${Math.max(1, visit.offered_to_count)} of up to 5. Each one has 2 minutes to answer.`}
          {left ? <span className="ml-1 font-semibold">Time left for this doctor: {left}.</span> : null}
        </Alert>
      ) : null}

      {visit.doctor && visit.status !== "offered" ? (
        <p className="mt-4 break-words text-sm text-ink">
          <span className="font-semibold">{visit.doctor.name}</span>
          <span className="text-ink-muted">
            , {visit.doctor.specialty}
            {visit.doctor.hospital ? `, ${visit.doctor.hospital}` : ""}
          </span>
        </p>
      ) : null}

      {visit.eta && (visit.status === "en_route" || visit.status === "accepted") ? (
        <p className="mt-2 text-sm text-ink">
          Doctor&apos;s estimate: about {visit.eta.minutes} minutes. The doctor typed this; it is not a tracked arrival time.
        </p>
      ) : null}

      <ol className="mt-5 space-y-3" aria-label="Steps of the visit">
        {STEPS.map((step, index) => {
          const at = visit[step.key] as string | null;
          const done = Boolean(at);
          return (
            <li key={step.label} className="flex items-start gap-3" aria-current={index === currentIndex ? "step" : undefined}>
              <span
                className={cn(
                  "mt-0.5 grid h-5 w-5 flex-shrink-0 place-items-center rounded-full",
                  done ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400",
                )}
              >
                {done ? <Check className="h-3 w-3" aria-hidden /> : <Circle className="h-2 w-2" aria-hidden />}
              </span>
              <div className="min-w-0">
                <p className={cn("text-sm", done ? "font-medium text-ink" : "text-ink-muted")}>{step.label}</p>
                {at ? <p className="text-xs text-ink-muted">{formatDateTime(at)}</p> : null}
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-5 flex items-start gap-2 text-xs leading-5 text-ink-muted">
        <PhoneCall className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden />
        If it gets worse or feels like an emergency, call 1122 or go to the nearest emergency department.
      </p>

      {error ? <Alert tone="error" className="mt-4">{error}</Alert> : null}
      {CANCELLABLE.has(visit.status) ? (
        <Button variant="danger" size="sm" className="mt-4" onClick={() => setConfirming(true)} loading={busy}>
          {busy ? "Cancelling..." : "Cancel this visit"}
        </Button>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title="Cancel this home visit?"
        description="The doctor will be told. You can send a new request afterwards."
        confirmLabel="Cancel the visit"
        pendingLabel="Cancelling..."
        pending={busy}
        onConfirm={() => {
          setConfirming(false);
          onCancel();
        }}
        onCancel={() => setConfirming(false)}
      />
    </section>
  );
}
