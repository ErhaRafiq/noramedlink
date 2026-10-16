"use client";

import Link from "next/link";
import { useState } from "react";
import { CalendarClock, CreditCard, RefreshCw, Star } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { TextAreaField } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { clinicDateTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { Appointment } from "@/lib/types";
import type { useMyAppointments } from "@/hooks/doctors/use-my-appointments";
import { MODE_LABEL } from "./BookingDialog";
import { SlotPicker } from "./SlotPicker";
import { StarInput } from "./Stars";

type Appointments = ReturnType<typeof useMyAppointments>;
type Action = { kind: "move" | "cancel" | "rate"; appointment: Appointment } | null;

const STATUS_LABEL: Record<string, string> = { BOOKED: "Booked", COMPLETED: "Completed", NO_SHOW: "Missed", CANCELLED: "Cancelled" };

function statusTone(status: string): BadgeTone {
  const value = status.toUpperCase();
  if (value === "BOOKED") return "success";
  if (value === "CANCELLED" || value === "NO_SHOW") return "danger";
  if (value === "COMPLETED") return "info";
  return "warning";
}

export function MyAppointments({ signedInAsPatient, list }: { signedInAsPatient: boolean; list: Appointments }) {
  const [action, setAction] = useState<Action>(null);
  const [now] = useState(() => Date.now()); // when this list was opened; a visit that has started can no longer be moved
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [slot, setSlot] = useState<string | null>(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");

  function open(kind: NonNullable<Action>["kind"], appointment: Appointment) {
    setAction({ kind, appointment });
    setError("");
    setSlot(null);
    setRating(0);
    setComment("");
  }

  function close() {
    if (!pending) setAction(null);
  }

  async function confirm() {
    if (!action || pending) return;
    setPending(true);
    const { kind, appointment } = action;
    const message =
      kind === "cancel"
        ? await list.cancel(appointment.id)
        : kind === "move"
          ? slot
            ? await list.reschedule(appointment.id, slot)
            : "Choose a new time."
          : await list.review(appointment.id, rating, comment.trim());
    setPending(false);
    if (message) setError(message);
    else setAction(null);
  }

  return (
    <aside aria-labelledby="my-appointments-title" className="h-fit rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <h2 id="my-appointments-title" className="text-base font-semibold text-ink">
          My appointments
        </h2>
        {signedInAsPatient ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void list.reload()}
            disabled={list.status === "loading"}
            aria-label="Refresh appointments"
            icon={<RefreshCw className={list.status === "loading" ? "h-4 w-4 animate-spin" : "h-4 w-4"} />}
          />
        ) : null}
      </div>

      <div className="mt-4 space-y-3">
        {!signedInAsPatient ? (
          <EmptyState
            icon={CalendarClock}
            title="Sign in to book"
            description="Patients can book and manage appointments after signing in."
            action={
              <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
                Sign in
              </Link>
            }
          />
        ) : list.status === "loading" && list.appointments.length === 0 ? (
          Array.from({ length: 2 }, (_, i) => (
            <div key={i} className="space-y-2 rounded-control border border-line p-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))
        ) : list.status === "error" ? (
          <Alert tone="error">{list.error}</Alert>
        ) : list.appointments.length === 0 ? (
          <EmptyState icon={CalendarClock} title="No appointments yet" description="Book a doctor from the list to see it here." />
        ) : (
          list.appointments.map((appointment) => <AppointmentItem key={appointment.id} appointment={appointment} now={now} onAction={open} />)
        )}
      </div>

      <Modal
        open={action?.kind === "move"}
        onClose={close}
        busy={pending}
        wide
        title="Move your appointment"
        description={action ? `${action.appointment.doctor_name}, now ${clinicDateTime(action.appointment.date)} PKT` : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={close} disabled={pending}>
              Keep current time
            </Button>
            <Button onClick={() => void confirm()} loading={pending} disabled={!slot}>
              {pending ? "Moving..." : "Move appointment"}
            </Button>
          </>
        }
      >
        {action?.kind === "move" && action.appointment.doctor_id ? (
          <div className="space-y-3">
            <SlotPicker doctorId={action.appointment.doctor_id} selected={slot} onSelect={setSlot} />
            {error ? <Alert tone="error">{error}</Alert> : null}
          </div>
        ) : null}
      </Modal>

      <Modal
        open={action?.kind === "rate"}
        onClose={close}
        busy={pending}
        title="Rate your visit"
        description={action?.appointment.doctor_name}
        footer={
          <>
            <Button variant="secondary" onClick={close} disabled={pending}>
              Not now
            </Button>
            <Button onClick={() => void confirm()} loading={pending} disabled={rating === 0} icon={<Star className="h-4 w-4" />}>
              {pending ? "Saving..." : "Save rating"}
            </Button>
          </>
        }
      >
        {action?.kind === "rate" ? (
          <div className="space-y-4">
            <StarInput value={rating} onChange={setRating} disabled={pending} />
            <TextAreaField label="Comment (optional)" rows={3} maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} hint="Other patients can read this. Do not include your name or medical details." />
            {error ? <Alert tone="error">{error}</Alert> : null}
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={action?.kind === "cancel"}
        title="Cancel this appointment?"
        description={
          action ? (
            <>
              <p>
                {action.appointment.doctor_name}, {clinicDateTime(action.appointment.date)} PKT. The time opens up for other patients.
              </p>
              {error ? <p className="mt-2 text-rose-700">{error}</p> : null}
            </>
          ) : null
        }
        confirmLabel="Cancel appointment"
        pendingLabel="Cancelling..."
        pending={pending}
        onConfirm={() => void confirm()}
        onCancel={close}
      />
    </aside>
  );
}

function AppointmentItem({ appointment, now, onAction }: { appointment: Appointment; now: number; onAction: (kind: "move" | "cancel" | "rate", appointment: Appointment) => void }) {
  const status = appointment.status.toUpperCase();
  const upcoming = status === "BOOKED" && new Date(appointment.date).getTime() > now;
  return (
    <article className="rounded-control border border-line p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink">{appointment.doctor_name}</h3>
          <p className="mt-0.5 text-xs text-ink-muted">{clinicDateTime(appointment.date)} PKT</p>
          <p className="text-xs text-ink-muted">
            {appointment.duration_minutes} min · {MODE_LABEL[appointment.mode] ?? appointment.mode}
          </p>
        </div>
        <Badge tone={statusTone(status)}>{STATUS_LABEL[status] ?? status.toLowerCase()}</Badge>
      </div>
      {appointment.reason || appointment.notes ? (
        <p className="mt-3 break-words rounded-control bg-surface-soft px-3 py-2 text-xs leading-5 text-slate-600">{appointment.reason ?? appointment.notes}</p>
      ) : null}
      <PaymentLine appointment={appointment} />
      {upcoming || (status === "COMPLETED" && !appointment.reviewed) ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {upcoming ? (
            <>
              <Button variant="secondary" size="sm" onClick={() => onAction("move", appointment)}>
                Reschedule
              </Button>
              <Button variant="danger" size="sm" onClick={() => onAction("cancel", appointment)}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="secondary" size="sm" icon={<Star className="h-3.5 w-3.5" />} onClick={() => onAction("rate", appointment)}>
              Rate this visit
            </Button>
          )}
        </div>
      ) : null}
      {status === "COMPLETED" && appointment.reviewed ? <p className="mt-2 text-xs text-ink-muted">Thanks for rating this visit.</p> : null}
    </article>
  );
}

function PaymentLine({ appointment }: { appointment: Appointment }) {
  const status = appointment.status.toUpperCase();
  if (appointment.payment_status.toUpperCase() === "PAID") {
    return (
      <p className="mt-2 text-xs font-medium text-emerald-700">
        Paid{appointment.consultation_fee ? ` · ${formatMoney(appointment.consultation_fee)}` : ""}
      </p>
    );
  }
  if (status !== "BOOKED" && status !== "COMPLETED") return null;
  if (!appointment.consultation_fee) return <p className="mt-2 text-xs text-ink-muted">Payment: the doctor has not set a fee yet.</p>;
  return (
    <Link
      href={`/payments?appointmentId=${appointment.id}`}
      className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-blue hover:underline"
    >
      <CreditCard className="h-3.5 w-3.5" aria-hidden />
      Pay {formatMoney(appointment.consultation_fee)}
    </Link>
  );
}
