"use client";

import { useEffect, useState } from "react";
import { CalendarCheck2, KeyRound } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextAreaField, TextField } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { clinicDateTime, formatDateTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { AppointmentDoctor, ConsultationMode, Review } from "@/lib/types";
import { PmdcBadge } from "./PmdcBadge";
import { RatingSummary } from "./Stars";
import { SlotPicker } from "./SlotPicker";

export const MODE_LABEL: Record<ConsultationMode, string> = { in_clinic: "In clinic", online: "Online", home: "Home visit" };

/** Choose a time, how to consult and why, then book. The server re-checks that the slot is still free. */
export function BookingDialog({
  doctor,
  busy,
  onClose,
  onBooked,
}: {
  doctor: AppointmentDoctor | null;
  busy?: { start: string; end: string }[];
  onClose: () => void;
  onBooked: (message: string) => void;
}) {
  return (
    <Modal open={doctor !== null} onClose={onClose} title={doctor ? `Book ${doctor.name}` : "Book"} description={doctor?.specialty} wide>
      {doctor ? <BookingForm key={doctor.id} doctor={doctor} busy={busy} onClose={onClose} onBooked={onBooked} /> : null}
    </Modal>
  );
}

function BookingForm({
  doctor,
  busy,
  onClose,
  onBooked,
}: {
  doctor: AppointmentDoctor;
  busy?: { start: string; end: string }[];
  onClose: () => void;
  onBooked: (message: string) => void;
}) {
  const [slot, setSlot] = useState<string | null>(null);
  const [mode, setMode] = useState<ConsultationMode>(doctor.consultation_modes[0] ?? "in_clinic");
  const [reason, setReason] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [shareFile, setShareFile] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [reviews, setReviews] = useState<Review[] | null>(null);

  useEffect(() => {
    let current = true;
    api
      .doctorReviews(doctor.id)
      .then((data) => current && setReviews(data))
      .catch(() => current && setReviews([]));
    return () => {
      current = false;
    };
  }, [doctor.id]);

  async function submit() {
    if (!slot || pending) return;
    setPending(true);
    setError("");
    try {
      const result = await api.bookAppointment({
        doctorId: doctor.id,
        date: slot,
        mode,
        reason: reason.trim(),
        patientAccessOtp: shareFile ? accessCode.trim() : "",
      });
      onBooked(`${result.message} ${clinicDateTime(result.appointment.date)} (PKT).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to book the appointment.");
      setPending(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <RatingSummary rating={doctor.rating} count={doctor.rating_count} />
          <PmdcBadge verified={doctor.pmdc_verified} checkedAt={doctor.pmdc_checked_at} />
        </div>
        <span className="text-ink-muted">
          {doctor.consultation_fee ? `${formatMoney(doctor.consultation_fee)} per consultation` : "Fee not set yet"}
        </span>
      </div>
      {reviews && reviews.length ? (
        <ul aria-label="Recent ratings" className="space-y-1.5 rounded-control bg-surface-soft p-3 text-sm">
          {reviews.slice(0, 2).map((review, i) => (
            <li key={i} className="break-words text-ink-muted">
              <span className="font-semibold text-ink">{review.rating}/5</span>
              {review.comment ? ` · ${review.comment}` : ""} <span className="text-xs">({formatDateTime(review.created_at)})</span>
            </li>
          ))}
        </ul>
      ) : null}

      <section aria-labelledby="pick-time">
        <h3 id="pick-time" className="mb-2 text-sm font-semibold text-ink">
          1. Choose a time
        </h3>
        <SlotPicker doctorId={doctor.id} selected={slot} onSelect={setSlot} busy={busy} />
      </section>

      <section aria-labelledby="pick-type">
        <h3 id="pick-type" className="mb-2 text-sm font-semibold text-ink">
          2. How would you like to consult?
        </h3>
        <div role="radiogroup" aria-label="Consultation type" className="flex flex-wrap gap-2">
          {(doctor.consultation_modes.length ? doctor.consultation_modes : (["in_clinic"] as ConsultationMode[])).map((option) => (
            <label
              key={option}
              className={cn(
                "cursor-pointer rounded-control border px-3.5 py-2 text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-blue",
                mode === option ? "border-brand-blue bg-blue-50 text-brand-blue" : "border-line bg-white text-slate-700 hover:border-line-strong",
              )}
            >
              <input type="radio" name="mode" value={option} checked={mode === option} onChange={() => setMode(option)} className="sr-only" />
              {MODE_LABEL[option]}
            </label>
          ))}
        </div>
      </section>

      <section aria-labelledby="pick-reason" className="space-y-3">
        <h3 id="pick-reason" className="text-sm font-semibold text-ink">
          3. Tell the doctor why
        </h3>
        <TextAreaField label="Reason for the visit" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Symptoms, how long you have had them, or anything the doctor should know" />
        <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={shareFile} onChange={(e) => setShareFile(e.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300 accent-brand-blue" />
          <span>
            <span className="inline-flex items-center gap-1.5 font-medium">
              <KeyRound className="h-3.5 w-3.5" aria-hidden /> Share my health file with this doctor for the visit
            </span>
            <span className="block text-xs text-ink-muted">Optional. Paste a one-time code from your dashboard; access ends when the consultation does.</span>
          </span>
        </label>
        {shareFile ? <TextField label="One-time code" inputMode="numeric" autoComplete="off" value={accessCode} onChange={(e) => setAccessCode(e.target.value)} /> : null}
      </section>

      {slot ? (
        <p className="rounded-control bg-blue-50 px-3 py-2 text-sm text-brand-blue">
          {clinicDateTime(slot)} PKT · {MODE_LABEL[mode]}
        </p>
      ) : null}
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onClose} disabled={pending}>
          Cancel
        </Button>
        <Button onClick={() => void submit()} loading={pending} disabled={!slot} icon={<CalendarCheck2 className="h-4 w-4" />}>
          {pending ? "Booking..." : "Confirm booking"}
        </Button>
      </div>
    </div>
  );
}
