"use client";

import { useState } from "react";
import { MapPin, Phone } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TextField } from "@/components/ui/field";
import { formatDateTime } from "@/lib/datetime";
import { coordinatesLabel } from "@/lib/location";
import type { DoctorHomeVisit, HomeVisitSummary } from "@/lib/types";
import { CloseForm } from "./CloseForm";
import { EmergencyReferral } from "./EmergencyReferral";

const TONE: Partial<Record<DoctorHomeVisit["status"], BadgeTone>> = {
  accepted: "info",
  en_route: "info",
  arrived: "success",
  completed: "warning",
  closed: "success",
  referred_emergency: "danger",
  cancelled: "neutral",
};

export type VisitActions = {
  busy: boolean;
  enRoute: (eta: number | null) => Promise<string | null>;
  arrived: () => Promise<string | null>;
  complete: () => Promise<string | null>;
  close: (summary: HomeVisitSummary) => Promise<string | null>;
  cancel: () => Promise<string | null>;
  escalate: () => Promise<string | null>;
};

/**
 * One visit the doctor accepted. While it is live the patient's phone, written address and place are shown with
 * the next step; once it has ended only the name and the summary remain.
 */
export function VisitItem({ visit, actions }: { visit: DoctorHomeVisit; actions: VisitActions }) {
  const [eta, setEta] = useState("");
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const live = ["accepted", "en_route", "arrived", "completed"].includes(visit.status);
  const { patient } = visit;

  async function step(action: () => Promise<string | null>) {
    setError((await action()) ?? "");
  }
  const minutes = eta.trim() === "" ? null : Number(eta);
  const etaOk = minutes === null || (Number.isInteger(minutes) && minutes >= 1 && minutes <= 240);

  return (
    <article aria-label={`Home visit with ${patient.name}`} className="rounded-control border border-line bg-surface-soft p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-words text-sm font-semibold text-ink">{patient.name}</p>
        <Badge tone={TONE[visit.status] ?? "neutral"}>{visit.status_label}</Badge>
      </div>
      <p className="mt-1 break-words text-sm leading-6 text-slate-700">{visit.reason}</p>
      <p className="mt-1 text-xs text-ink-muted">
        {visit.specialty} · {visit.distance} · accepted {visit.accepted_at ? formatDateTime(visit.accepted_at) : ""}
      </p>

      {live && patient.phone ? (
        <dl className="mt-3 space-y-1.5 rounded-control bg-white p-3 text-sm">
          <div className="flex items-start gap-2">
            <Phone className="mt-0.5 h-4 w-4 flex-shrink-0 text-ink-muted" aria-hidden />
            <dd className="min-w-0 break-words">
              <span className="sr-only">Phone: </span>
              <a href={`tel:${patient.phone.replace(/[^0-9+]/g, "")}`} className="font-medium text-brand-blue hover:underline">
                {patient.phone}
              </a>
            </dd>
          </div>
          <div className="flex items-start gap-2">
            <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-ink-muted" aria-hidden />
            <dd className="min-w-0 break-words">
              <span className="sr-only">Address: </span>
              {patient.address_text}
              {patient.latitude !== null && patient.longitude !== null ? (
                <span className="block text-xs text-ink-muted">
                  Coordinates {coordinatesLabel(patient.latitude, patient.longitude)} ({patient.location}). Straight-line only, not a route.
                </span>
              ) : null}
            </dd>
          </div>
        </dl>
      ) : null}

      {visit.eta ? <p className="mt-2 text-xs text-ink-muted">Your estimate: about {visit.eta.minutes} minutes (shown to the patient as the doctor&apos;s estimate).</p> : null}

      {visit.summary ? (
        <dl className="mt-3 space-y-1 rounded-control bg-white p-3 text-sm">
          <div><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Found</dt><dd className="break-words">{visit.summary.findings}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Advice</dt><dd className="break-words">{visit.summary.advice}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Follow-up</dt><dd className="break-words">{visit.summary.follow_up}</dd></div>
        </dl>
      ) : null}

      {error ? <Alert tone="error" className="mt-3">{error}</Alert> : null}

      {visit.status === "accepted" ? (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <TextField
            label="Your estimate in minutes (optional)"
            inputMode="numeric"
            placeholder="20"
            value={eta}
            onChange={(e) => setEta(e.target.value)}
            error={etaOk ? "" : "Enter whole minutes, 1 to 240."}
            wrapperClassName="w-56 max-w-full"
          />
          <Button size="sm" loading={actions.busy} disabled={!etaOk} onClick={() => void step(() => actions.enRoute(minutes))}>
            {actions.busy ? "Working..." : "I am on my way"}
          </Button>
        </div>
      ) : null}
      {visit.status === "en_route" ? (
        <Button size="sm" className="mt-3" loading={actions.busy} onClick={() => void step(actions.arrived)}>
          {actions.busy ? "Working..." : "I have arrived"}
        </Button>
      ) : null}
      {visit.status === "arrived" ? (
        <Button size="sm" className="mt-3" loading={actions.busy} onClick={() => void step(actions.complete)}>
          {actions.busy ? "Working..." : "The visit is finished"}
        </Button>
      ) : null}
      {visit.status === "completed" ? <CloseForm busy={actions.busy} onClose={actions.close} /> : null}

      {live ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {visit.status !== "completed" ? (
            <Button variant="secondary" size="sm" onClick={() => setCancelling(true)} disabled={actions.busy}>
              Cancel this visit
            </Button>
          ) : null}
          <EmergencyReferral busy={actions.busy} onRefer={() => void step(actions.escalate)} />
        </div>
      ) : null}
      <ConfirmDialog
        open={cancelling}
        title="Cancel this home visit?"
        description="The patient will be told and can send a new request."
        confirmLabel="Cancel the visit"
        pendingLabel="Cancelling..."
        pending={actions.busy}
        onConfirm={() => {
          setCancelling(false);
          void step(actions.cancel);
        }}
        onCancel={() => setCancelling(false)}
      />
    </article>
  );
}
