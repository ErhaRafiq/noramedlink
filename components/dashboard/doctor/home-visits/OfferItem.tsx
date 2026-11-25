"use client";

import { Check, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useNow } from "@/hooks/use-now";
import type { DoctorHomeVisitOffer } from "@/lib/types";
import { EmergencyReferral } from "./EmergencyReferral";

function timeLeft(expiresAt: string, now: number) {
  const left = Math.max(0, Math.round((new Date(expiresAt).getTime() - now) / 1000));
  return { left, text: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` };
}

/**
 * A request waiting for this doctor. The reason and a rounded straight-line distance are shown; the patient's
 * name, phone and address only after the doctor accepts.
 */
export function OfferItem({
  offer,
  busy,
  onAccept,
  onDecline,
  onRefer,
}: {
  offer: DoctorHomeVisitOffer;
  busy: boolean;
  onAccept: () => void;
  onDecline: () => void;
  onRefer: () => void;
}) {
  const now = useNow(true);
  const { left, text } = timeLeft(offer.expires_at, now);
  return (
    <article aria-label="Home visit request waiting for you" className="rounded-control border border-brand-blue/30 bg-blue-50/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">New request · {offer.specialty}</p>
        <p className="text-xs font-semibold text-brand-blue" role="timer" aria-label="Time left to answer">
          {left > 0 ? `Answer within ${text}` : "Time is up"}
        </p>
      </div>
      <p className="mt-2 break-words text-sm leading-6 text-slate-700">{offer.reason}</p>
      <p className="mt-1 text-xs text-ink-muted">
        {offer.distance}. The patient&apos;s name, phone and address are shown after you accept.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" icon={<Check className="h-4 w-4" />} onClick={onAccept} loading={busy} disabled={left === 0}>
          {busy ? "Working..." : "Accept"}
        </Button>
        <Button variant="secondary" size="sm" icon={<X className="h-4 w-4" />} onClick={onDecline} disabled={busy}>
          Decline
        </Button>
        <EmergencyReferral busy={busy} onRefer={onRefer} />
      </div>
    </article>
  );
}
